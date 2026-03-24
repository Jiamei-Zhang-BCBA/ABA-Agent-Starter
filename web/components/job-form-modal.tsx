"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Feature, FormField } from "@/types";

interface JobFormModalProps {
  feature: Feature | null;
  open: boolean;
  onClose: () => void;
}

interface FieldOption {
  value: string;
  label: string;
}

interface SchemaField extends FormField {
  options?: FieldOption[];
}

interface FeatureSchema {
  id: string;
  form_schema: { fields: SchemaField[] };
}

export function JobFormModal({ feature, open, onClose }: JobFormModalProps) {
  const router = useRouter();
  const [schema, setSchema] = useState<FeatureSchema | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [schemaLoading, setSchemaLoading] = useState(false);

  useEffect(() => {
    if (!feature || !open) return;
    setSchemaLoading(true);
    setFormData({});
    setFiles([]);
    api
      .get<FeatureSchema>(`/features/${feature.id}/schema`)
      .then(setSchema)
      .catch(() => toast.error("加载表单失败"))
      .finally(() => setSchemaLoading(false));
  }, [feature, open]);

  function updateField(name: string, value: string) {
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!feature) return;

    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("feature_id", feature.id);

      // Extract client_id from form data if present
      const clientField = schema?.form_schema.fields.find(
        (f) => f.type === "select_client",
      );
      if (clientField && formData[clientField.name]) {
        fd.append("client_id", formData[clientField.name]);
      }

      fd.append("form_data", JSON.stringify(formData));
      for (const file of files) {
        fd.append("files", file);
      }

      await api.post("/jobs", fd);
      toast.success("任务已提交");
      onClose();
      router.push("/jobs");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "提交失败");
    } finally {
      setLoading(false);
    }
  }

  function renderField(field: SchemaField) {
    const { name, label, type, required } = field;

    switch (type) {
      case "text":
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>{label}{required && " *"}</Label>
            <Input
              id={name}
              value={formData[name] || ""}
              onChange={(e) => updateField(name, e.target.value)}
              required={required}
            />
          </div>
        );
      case "number":
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>{label}{required && " *"}</Label>
            <Input
              id={name}
              type="number"
              value={formData[name] || ""}
              onChange={(e) => updateField(name, e.target.value)}
              required={required}
            />
          </div>
        );
      case "textarea":
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>{label}{required && " *"}</Label>
            <Textarea
              id={name}
              value={formData[name] || ""}
              onChange={(e) => updateField(name, e.target.value)}
              rows={4}
              required={required}
            />
          </div>
        );
      case "select_client":
      case "select_staff":
        return (
          <div key={name} className="space-y-2">
            <Label>{label}{required && " *"}</Label>
            <Select
              value={formData[name] || ""}
              onValueChange={(v) => updateField(name, v ?? "")}
              required={required}
            >
              <SelectTrigger>
                <SelectValue placeholder="请选择" />
              </SelectTrigger>
              <SelectContent>
                {(field.options || []).map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        );
      case "file":
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>{label}{required && " *"}</Label>
            <Input
              id={name}
              type="file"
              accept={field.accept?.join(",") || undefined}
              multiple
              onChange={(e) => {
                const fileList = e.target.files;
                if (fileList) {
                  setFiles(Array.from(fileList));
                }
              }}
              required={required}
            />
          </div>
        );
      default:
        return null;
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {feature?.icon} {feature?.display_name}
          </DialogTitle>
        </DialogHeader>
        {schemaLoading ? (
          <div className="py-8 text-center text-gray-400">加载表单中...</div>
        ) : schema ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            {schema.form_schema.fields.map(renderField)}
            <div className="flex justify-end space-x-2 pt-4">
              <Button type="button" variant="outline" onClick={onClose}>
                取消
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? "提交中..." : "提交任务"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="py-8 text-center text-gray-400">暂无表单</div>
        )}
      </DialogContent>
    </Dialog>
  );
}
