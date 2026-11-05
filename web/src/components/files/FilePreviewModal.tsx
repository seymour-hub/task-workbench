import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, ExternalLink, FolderOpen, MonitorPlay } from "lucide-react";
import { api } from "../../api/client";
import { previewUrl } from "../../lib/files";
import { Modal } from "../ui/primitives";

export interface PreviewItem {
  path: string;
  title: string;
}

function extensionOf(path: string): string {
  const clean = path.split("?")[0];
  const dot = clean.lastIndexOf(".");
  return dot >= 0 ? clean.slice(dot).toLowerCase() : "";
}

function kindOf(path: string): "url" | "image" | "pdf" | "html" | "video" | "audio" | "text" | "unsupported" {
  if (path.startsWith("http://") || path.startsWith("https://")) return "url";
  const ext = extensionOf(path);
  if ([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"].includes(ext)) return "image";
  if (ext === ".pdf") return "pdf";
  if ([".html", ".htm"].includes(ext)) return "html";
  if ([".mp4", ".mov", ".webm"].includes(ext)) return "video";
  if ([".mp3", ".wav", ".m4a"].includes(ext)) return "audio";
  if ([".txt", ".md", ".csv", ".json", ".xml", ".log"].includes(ext)) return "text";
  return "unsupported";
}

export default function FilePreviewModal({
  item,
  onClose,
}: {
  item: PreviewItem | null;
  onClose: () => void;
}) {
  const systemOpen = useMutation({
    mutationFn: (path: string) => api.openFile(path),
    onError: (error: Error) => toast.error(error.message),
  });
  const reveal = useMutation({
    mutationFn: (path: string) => api.revealFile(path),
    onError: (error: Error) => toast.error(error.message),
  });

  if (!item) return null;
  const kind = kindOf(item.path);
  const url = previewUrl(item.path);
  const isLocal = kind !== "url";

  return (
    <Modal
      open={Boolean(item)}
      onClose={onClose}
      title={item.title}
      width="max-w-6xl"
      footer={
        <>
          {isLocal ? (
            <>
              <button
                className="btn-ghost"
                onClick={() => reveal.mutate(item.path)}
              >
                <FolderOpen size={14} /> 打开文件夹
              </button>
              <a
                className="btn-ghost"
                href={`${url}${url.includes("?") ? "&" : "?"}download=true`}
                onClick={(event) => event.stopPropagation()}
              >
                <Download size={14} /> 下载
              </a>
              <button
                className="btn-ghost"
                onClick={() => systemOpen.mutate(item.path)}
              >
                <MonitorPlay size={14} /> 默认程序打开
              </button>
            </>
          ) : null}
          <button
            className="btn-primary"
            onClick={() => window.open(url, "_blank")}
          >
            <ExternalLink size={14} /> 新标签打开
          </button>
        </>
      }
    >
      <div className="h-[70vh] overflow-hidden rounded-xl border border-ink-700/60 bg-ink-950/60">
        {kind === "image" ? (
          <div className="flex h-full w-full items-center justify-center bg-[#0b0f18]">
            <img
              src={url}
              alt={item.title}
              className="max-h-full max-w-full object-contain"
            />
          </div>
        ) : kind === "pdf" || kind === "html" || kind === "text" ? (
          <iframe
            src={url}
            title={item.title}
            className="h-full w-full bg-white"
            sandbox={
              kind === "html"
                ? "allow-scripts allow-forms allow-modals allow-popups"
                : undefined
            }
          />
        ) : kind === "video" ? (
          <div className="flex h-full w-full items-center justify-center bg-black">
            <video src={url} controls className="max-h-full max-w-full" />
          </div>
        ) : kind === "audio" ? (
          <div className="flex h-full w-full items-center justify-center bg-ink-900 p-8">
            <audio src={url} controls className="w-full max-w-xl" />
          </div>
        ) : kind === "url" ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm text-mist-200">这是一个外部链接</p>
            <p className="max-w-lg break-all text-xs text-mist-500">{item.path}</p>
            <button className="btn-primary" onClick={() => window.open(url, "_blank")}>
              <ExternalLink size={14} /> 在浏览器打开
            </button>
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
            <MonitorPlay size={30} className="text-mist-500" />
            <p className="text-sm font-medium text-mist-200">
              该格式无法在工作台内预览
            </p>
            <p className="max-w-md text-xs leading-5 text-mist-500">
              PPT / Word / Excel / 压缩包需要系统程序打开。如果窗口被浏览器挡住，
              可以使用“打开文件夹”或“下载”后再打开。
            </p>
            <div className="mt-2 flex gap-2">
              <button
                className="btn-ghost"
                onClick={() => systemOpen.mutate(item.path)}
              >
                <MonitorPlay size={14} /> 用默认程序打开
              </button>
              <button
                className="btn-ghost"
                onClick={() => reveal.mutate(item.path)}
              >
                <FolderOpen size={14} /> 打开文件夹
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
