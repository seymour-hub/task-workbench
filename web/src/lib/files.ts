const PREVIEW_EXTENSIONS = new Set([
  ".html",
  ".htm",
  ".pdf",
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".svg",
  ".webp",
  ".mp4",
  ".mov",
  ".webm",
  ".mp3",
  ".wav",
  ".txt",
  ".md",
  ".csv",
  ".json",
  ".xml",
]);

export function isBrowserPreviewable(path: string): boolean {
  if (!path) return false;
  if (path.startsWith("http://") || path.startsWith("https://")) return true;
  const clean = path.split("?")[0];
  const dot = clean.lastIndexOf(".");
  const ext = dot >= 0 ? clean.slice(dot).toLowerCase() : "";
  return PREVIEW_EXTENSIONS.has(ext);
}

export function previewUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `/api/files/serve?path=${encodeURIComponent(path)}`;
}

export function openDeliverableFile(
  path: string,
  systemOpen: (path: string) => void,
): void {
  if (isBrowserPreviewable(path)) {
    const popup = window.open(previewUrl(path), "_blank");
    popup?.focus();
    return;
  }
  systemOpen(path);
}
