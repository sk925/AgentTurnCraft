/** 与后端 `ModelType` 枚举取值一致 */
export const CHAT_MODEL_TYPE_OPTIONS = [
  { value: 'text_generation', label: '文本生成' },
  { value: 'embedding', label: 'Embedding（向量化）' },
  { value: 'image_generation', label: '图像生成' },
  { value: 'audio_generation', label: '音频生成' },
  { value: 'video_generation', label: '视频生成' },
  { value: 'code_generation', label: '代码生成' },
  { value: 'data_generation', label: '数据生成' },
] as const;
