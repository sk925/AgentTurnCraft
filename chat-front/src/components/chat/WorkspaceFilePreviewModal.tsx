import { useEffect, useRef, useState } from 'react';
import { Button, Modal, Spin, Typography, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import type { WorkspaceArtifactFile } from '../../api';
import { chatWindowApi, getBackendErrorMessage } from '../../api';
import {
  getWorkspacePreviewKind,
  type WorkspacePreviewKind,
} from './workspacePreview';
import './WorkspaceFilePreviewModal.css';

type WorkspaceFilePreviewModalProps = {
  open: boolean;
  sessionId: string | null;
  file: WorkspaceArtifactFile | null;
  onClose: () => void;
};

type PreviewState = {
  kind: WorkspacePreviewKind;
  blobUrl: string;
  textContent: string;
  mime: string;
};

export default function WorkspaceFilePreviewModal({
  open,
  sessionId,
  file,
  onClose,
}: WorkspaceFilePreviewModalProps) {
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  const revokeBlobUrl = () => {
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = null;
    }
  };

  useEffect(() => {
    if (!open || !file || !sessionId) {
      revokeBlobUrl();
      setPreview(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    const kind = getWorkspacePreviewKind(file.name);

    const load = async () => {
      setLoading(true);
      setPreview(null);
      revokeBlobUrl();
      try {
        const { blob, mime } = await chatWindowApi.fetchWorkspaceFile(sessionId, file.relative_path);
        if (cancelled) {
          return;
        }

        if (kind === 'unsupported') {
          setPreview({ kind, blobUrl: '', textContent: '', mime });
          return;
        }

        if (kind === 'text') {
          const textContent = await blob.text();
          if (cancelled) {
            return;
          }
          setPreview({ kind, blobUrl: '', textContent, mime });
          return;
        }

        const blobUrl = URL.createObjectURL(blob);
        blobUrlRef.current = blobUrl;
        setPreview({ kind, blobUrl, textContent: '', mime });
      } catch (error) {
        if (!cancelled) {
          message.error(getBackendErrorMessage(error, '加载预览失败'));
          onClose();
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
      revokeBlobUrl();
    };
  }, [open, file, sessionId, onClose]);

  const handleDownload = async () => {
    if (!file || !sessionId) {
      return;
    }
    try {
      const { blob } = await chatWindowApi.fetchWorkspaceFile(sessionId, file.relative_path);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = file.name;
      anchor.rel = 'noopener';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '下载失败'));
    }
  };

  const renderBody = () => {
    if (loading) {
      return (
        <div className="workspace-preview__loading">
          <Spin tip="加载中…" />
        </div>
      );
    }

    if (!preview || !file) {
      return null;
    }

    if (preview.kind === 'unsupported') {
      return (
        <div className="workspace-preview__unsupported">
          <Typography.Paragraph type="secondary">
            当前文件类型暂不支持在线预览，你可以下载后在本地打开。
          </Typography.Paragraph>
          <Typography.Text type="secondary">{file.relative_path}</Typography.Text>
        </div>
      );
    }

    if (preview.kind === 'text') {
      return (
        <pre className="workspace-preview__text" aria-label={`${file.name} 文本预览`}>
          {preview.textContent}
        </pre>
      );
    }

    if (preview.kind === 'image') {
      return (
        <div className="workspace-preview__image-wrap">
          <img
            className="workspace-preview__image"
            src={preview.blobUrl}
            alt={file.name}
          />
        </div>
      );
    }

    return (
      <iframe
        className="workspace-preview__iframe"
        title={`${file.name} 预览`}
        src={preview.blobUrl}
        sandbox={preview.kind === 'html' ? 'allow-same-origin' : undefined}
      />
    );
  };

  return (
    <Modal
      className="workspace-preview-modal"
      title={file?.name ?? '文件预览'}
      open={open}
      onCancel={onClose}
      width="min(960px, 92vw)"
      destroyOnHidden
      footer={[
        <Button key="download" icon={<DownloadOutlined />} onClick={() => void handleDownload()}>
          下载
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          关闭
        </Button>,
      ]}
    >
      {file ? (
        <Typography.Text type="secondary" className="workspace-preview__meta">
          {file.relative_path}
        </Typography.Text>
      ) : null}
      <div className="workspace-preview__body">{renderBody()}</div>
    </Modal>
  );
}
