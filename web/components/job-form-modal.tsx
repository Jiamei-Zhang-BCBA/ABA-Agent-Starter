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
import { FeatureIcon } from "@/components/feature-icon";
import type { Feature, FormField, ExpectedOutput } from "@/types";

interface JobFormModalProps {
  feature: Feature | null;
  open: boolean;
  onClose: () => void;
  defaultClientId?: string;
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
  expected_outputs?: ExpectedOutput[];
  is_destructive?: boolean;
}

const OP_BADGE: Record<ExpectedOutput["op"], { label: string; className: string }> = {
  create: { label: "新建", className: "bg-emerald-100 text-emerald-700" },
  edit: { label: "覆盖编辑", className: "bg-amber-100 text-amber-700" },
  append: { label: "追加", className: "bg-sky-100 text-sky-700" },
};

export function JobFormModal({ feature, open, onClose, defaultClientId }: JobFormModalProps) {
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
      .then((s) => {
        setSchema(s);
        // Pre-fill client field if defaultClientId is provided
        if (defaultClientId) {
          const clientField = s.form_schema.fields.find(
            (f) => f.type === "select_client",
          );
          if (clientField) {
            setFormData((prev) => ({ ...prev, [clientField.name]: defaultClientId }));
          }
        }
      })
      .catch(() => toast.error("加载表单失败"))
      .finally(() => setSchemaLoading(false));
  }, [feature, open, defaultClientId]);

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

  function fieldHelp(field: SchemaField) {
    if (!field.help_text) return null;
    return <p className="text-xs text-gray-500 leading-relaxed">{field.help_text}</p>;
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
              placeholder={field.placeholder}
              onChange={(e) => updateField(name, e.target.value)}
              required={required}
            />
            {fieldHelp(field)}
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
              placeholder={field.placeholder}
              onChange={(e) => updateField(name, e.target.value)}
              required={required}
            />
            {fieldHelp(field)}
          </div>
        );
      case "textarea":
        return (
          <div key={name} className="space-y-2">
            <Label htmlFor={name}>{label}{required && " *"}</Label>
            <Textarea
              id={name}
              value={formData[name] || ""}
              placeholder={field.placeholder}
              onChange={(e) => updateField(name, e.target.value)}
              rows={4}
              required={required}
            />
            {fieldHelp(field)}
          </div>
        );
      case "select":
        return (
          <div key={name} className="space-y-2">
            <Label>{label}{required && " *"}</Label>
            <Select
              value={formData[name] || ""}
              onValueChange={(v) => updateField(name, v ?? "")}
              required={required}
            >
              <SelectTrigger>
                <SelectValue placeholder={field.placeholder || "请选择"} />
              </SelectTrigger>
              <SelectContent>
                {(field.options || []).map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {fieldHelp(field)}
          </div>
        );
      case "select_client": {
        // When opened from a client page, lock the client field
        if (defaultClientId && formData[name]) {
          const selectedOpt = (field.options || []).find((o) => o.value === formData[name]);
          return (
            <div key={name} className="space-y-2">
              <Label>{label}</Label>
              <div className="border rounded-md px-3 py-2 bg-gray-50 text-sm text-gray-700">
                {selectedOpt?.label || formData[name]}
              </div>
            </div>
          );
        }
        // Fall through to normal select
      }
      // eslint-disable-next-line no-fallthrough
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
            {fieldHelp(field)}
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
            {fieldHelp(field)}
          </div>
        );
      default:
        return null;
    }
  }

  function renderExpectedOutputs() {
    const outputs = schema?.expected_outputs || [];
    if (outputs.length === 0) return null;
    return (
      <div className="border rounded-md bg-slate-50 p-3 space-y-2">
        <p className="text-xs font-semibold text-slate-700">📄 本次操作将产出/修改以下文件：</p>
        <ul className="space-y-1.5">
          {outputs.map((o, idx) => {
            const badge = OP_BADGE[o.op] || OP_BADGE.create;
            return (
              <li key={idx} className="flex items-start gap-2 text-xs">
                <span className={`shrink-0 px-1.5 py-0.5 rounded font-medium ${badge.className}`}>
                  {badge.label}
                </span>
                <div className="min-w-0 flex-1">
                  <code className="text-[11px] text-slate-600 break-all">{o.path}</code>
                  <p className="text-slate-500 mt-0.5">{o.description}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }

  function renderDestructiveBanner() {
    if (!schema?.is_destructive) return null;
    return (
      <div className="border border-red-300 bg-red-50 rounded-md p-3 text-sm text-red-800">
        <p className="font-semibold">⚠️ 不可逆操作</p>
        <p className="text-xs mt-1 leading-relaxed">
          本操作会覆盖或永久变更现有档案/状态。执行前请仔细确认表单内容。
        </p>
      </div>
    );
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {feature && (
              <FeatureIcon
                name={feature.icon || "wrench"}
                className="w-5 h-5 text-indigo-500"
              />
            )}
            <span>{feature?.display_name}</span>
          </DialogTitle>
        </DialogHeader>
        {schemaLoading ? (
          <div className="py-8 text-center text-gray-400">加载表单中...</div>
        ) : schema ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            {renderDestructiveBanner()}
            {schema.form_schema.fields.map(renderField)}
            {renderExpectedOutputs()}
            <div className="flex justify-end space-x-2 pt-4">
              <Button type="button" variant="outline" onClick={onClose}>
                取消
              </Button>
              <Button
                type="submit"
                disabled={loading}
                variant={schema.is_destructive ? "destructive" : "default"}
              >
                {loading ? "提交中..." : schema.is_destructive ? "确认执行 (不可逆)" : "提交任务"}
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
