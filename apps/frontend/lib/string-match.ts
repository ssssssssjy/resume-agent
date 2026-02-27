/**
 * 字符串匹配工具函数
 * 用于处理 Agent 返回的 oldString 与实际内容的匹配
 */

/**
 * Levenshtein 距离计算（用于模糊匹配）
 */
export function levenshteinDistance(a: string, b: string): number {
  const matrix: number[][] = [];
  for (let i = 0; i <= b.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= a.length; j++) {
    matrix[0][j] = j;
  }
  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1, // 替换
          matrix[i][j - 1] + 1,     // 插入
          matrix[i - 1][j] + 1      // 删除
        );
      }
    }
  }
  return matrix[b.length][a.length];
}

/**
 * 计算字符串相似度 (0-1, 1 为完全匹配)
 */
export function stringSimilarity(a: string, b: string): number {
  if (a === b) return 1;
  if (a.length === 0 || b.length === 0) return 0;
  const distance = levenshteinDistance(a, b);
  const maxLen = Math.max(a.length, b.length);
  return 1 - distance / maxLen;
}

export interface MatchResult {
  found: boolean;
  matchedString: string;
}

/**
 * 三层匹配策略：精确匹配 → trim 匹配 → 模糊匹配
 * @param targetString - 要查找的字符串
 * @param content - 内容文本
 * @param similarityThreshold - 模糊匹配阈值，默认 0.85
 * @returns 匹配结果
 */
export function findMatchingString(
  targetString: string,
  content: string,
  similarityThreshold = 0.85
): MatchResult {
  // 第一层：精确匹配
  if (content.includes(targetString)) {
    return { found: true, matchedString: targetString };
  }

  const trimmedTarget = targetString.trim();
  const lines = content.split("\n");

  // 第二层：trim 匹配
  for (const line of lines) {
    if (line.trim() === trimmedTarget || line.includes(trimmedTarget)) {
      return { found: true, matchedString: line };
    }
  }

  // 第三层：模糊匹配
  let bestMatch = { line: "", similarity: 0 };
  for (const line of lines) {
    const similarity = stringSimilarity(line.trim(), trimmedTarget);
    if (similarity > bestMatch.similarity && similarity >= similarityThreshold) {
      bestMatch = { line, similarity };
    }
  }

  if (bestMatch.similarity >= similarityThreshold) {
    return { found: true, matchedString: bestMatch.line };
  }

  return { found: false, matchedString: targetString };
}
