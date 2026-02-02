"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText } from "lucide-react";

interface PDFUploadProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export function PDFUpload({ onFileSelect, disabled = false }: PDFUploadProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (file && file.type === "application/pdf") {
        onFileSelect(file);
      }
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
    },
    maxFiles: 1,
    disabled,
  });

  return (
    <div
      {...getRootProps()}
      className={`
        flex flex-col items-center justify-center h-full
        border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all
        ${isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"}
        ${disabled ? "opacity-50 cursor-not-allowed" : ""}
      `}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-4">
        <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
          {isDragActive ? (
            <FileText className="w-8 h-8 text-primary" />
          ) : (
            <Upload className="w-8 h-8 text-primary" />
          )}
        </div>
        {isDragActive ? (
          <p className="text-primary font-medium">放开以上传文件...</p>
        ) : (
          <div className="space-y-2">
            <p className="text-lg font-medium">上传简历 PDF</p>
            <p className="text-sm text-muted-foreground">
              拖拽文件到这里，或点击选择
            </p>
            <p className="text-xs text-muted-foreground">
              仅支持 PDF 格式
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
