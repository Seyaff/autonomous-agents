"use client";

import React, { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import API from "@/lib/axios-client";

interface SettingsProps {
  children?: React.ReactNode;
}

export default function Settings({ children }: SettingsProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };


  const handleUpload = (e:any) => {

    
    if (!file) return;

    setIsUploading(true);

    
  }
  
    
  return (
    <main className="container max-w-2xl mx-auto py-8 px-4">
      <form onSubmit={handleUpload} className="space-y-6 rounded-lg p-6">
        <div className="space-y-1.5">
          <h1 className="text-2xl font-semibold tracking-tight">Upload Document</h1>
          <p className="text-sm text-muted-foreground">
            Select a PDF file from your device to upload.
          </p>
        </div>

        <div className="grid w-full items-center gap-1.5">
          <Label htmlFor="pdf-upload">PDF Document</Label>
          <Input
            id="pdf-upload"
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
          />
        </div>

        {children}

        <div>
          <Button type="submit" disabled={!file || isUploading}>
            {isUploading ? "Uploading..." : "Upload File"}
          </Button>
        </div>
      </form>
    </main>
  );
}