export type WorkspacePreviewKind = 'text' | 'html' | 'pdf' | 'image' | 'unsupported';

const TEXT_EXTENSIONS = new Set([
  'txt',
  'md',
  'markdown',
  'json',
  'csv',
  'xml',
  'log',
  'yaml',
  'yml',
  'js',
  'ts',
  'tsx',
  'jsx',
  'css',
  'py',
  'html',
]);

const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp']);

export function fileExtension(fileName: string): string {
  const parts = fileName.split('.');
  if (parts.length < 2) {
    return '';
  }
  return (parts.pop() ?? '').toLowerCase();
}

export function getWorkspacePreviewKind(fileName: string): WorkspacePreviewKind {
  const ext = fileExtension(fileName);
  if (ext === 'pdf') {
    return 'pdf';
  }
  if (ext === 'html' || ext === 'htm') {
    return 'html';
  }
  if (IMAGE_EXTENSIONS.has(ext)) {
    return 'image';
  }
  if (TEXT_EXTENSIONS.has(ext)) {
    return 'text';
  }
  return 'unsupported';
}

export function isWorkspaceFilePreviewable(fileName: string): boolean {
  return getWorkspacePreviewKind(fileName) !== 'unsupported';
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return '-';
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(bytes >= 10 * 1024 ? 0 : 1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatModifiedTime(ts: number): string {
  if (!Number.isFinite(ts) || ts <= 0) {
    return '';
  }
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return '';
  }
}
