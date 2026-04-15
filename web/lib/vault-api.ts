import { api } from "@/lib/api";
import type {
  VaultRootsResponse,
  VaultTreeResponse,
  VaultFileContent,
} from "@/types";

export interface AIReviseResponse {
  revised_content: string;
  input_tokens: number;
  output_tokens: number;
}

export const vaultApi = {
  getRoots(): Promise<VaultRootsResponse> {
    return api.get<VaultRootsResponse>("/vault/roots");
  },

  listDirectory(prefix: string): Promise<VaultTreeResponse> {
    return api.get<VaultTreeResponse>(
      `/vault/tree?prefix=${encodeURIComponent(prefix)}`,
    );
  },

  readFile(path: string): Promise<VaultFileContent> {
    return api.get<VaultFileContent>(
      `/vault/read?path=${encodeURIComponent(path)}`,
    );
  },

  writeFile(path: string, content: string): Promise<{ path: string; message: string }> {
    return api.put<{ path: string; message: string }>("/vault/write", { path, content });
  },

  aiRevise(content: string, instruction: string, vaultPath?: string): Promise<AIReviseResponse> {
    return api.post<AIReviseResponse>("/reviews/ai-revise", {
      content,
      instruction,
      vault_path: vaultPath,
    });
  },
};
