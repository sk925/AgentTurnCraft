import { useState, useEffect } from 'react';
import { Table, Button, Modal, Upload, message, Popconfirm, Card } from 'antd';
import { UploadOutlined, DeleteOutlined } from '@ant-design/icons';
import { skillsApi } from '../api';
import type { Skill } from '../api';

export default function SkillsPage() {
  const userId = 1;
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const data = await skillsApi.getAll(userId);
      setSkills(data);
    } catch (error) {
      message.error('获取技能列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSkills();
  }, []);

  const handleUpload = async (file: File) => {
    try {
      await skillsApi.upload(userId, file);
      message.success('上传成功');
      setUploadModalVisible(false);
      fetchSkills();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '上传失败');
    }
    return false;
  };

  const handleDelete = async (id: number) => {
    try {
      await skillsApi.delete(userId, id);
      message.success('删除成功');
      fetchSkills();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '文件路径',
      dataIndex: 'file_path',
      key: 'file_path',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'create_time',
      key: 'create_time',
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Skill) => (
        <Popconfirm
          title="确定删除该技能吗？"
          onConfirm={() => handleDelete(record.id)}
          okText="确定"
          cancelText="取消"
        >
          <Button danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Card
      title="技能管理"
      extra={
        <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadModalVisible(true)}>
          上传技能
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={skills}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="上传技能"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
      >
        <Upload.Dragger
          accept=".zip"
          beforeUpload={handleUpload}
          showUploadList={false}
          maxCount={1}
        >
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽 .zip 文件上传</p>
          <p className="ant-upload-hint">上传符合 openclaw 规范的技能压缩包</p>
        </Upload.Dragger>
      </Modal>
    </Card>
  );
}
