import { z } from 'zod'

export const loginSchema = z.object({
  username: z
    .string()
    .min(1, '请输入用户名')
    .min(2, '用户名至少2个字符')
    .max(50, '用户名不能超过50个字符'),
  password: z
    .string()
    .min(1, '请输入密码')
    .min(6, '密码至少6个字符')
    .max(100, '密码不能超过100个字符'),
})

export type LoginFormValues = z.infer<typeof loginSchema>

export const registerSchema = z
  .object({
    username: z
      .string()
      .min(1, '请输入用户名')
      .min(3, '用户名至少3个字符')
      .max(50, '用户名不能超过50个字符')
      .regex(/^[a-zA-Z0-9_]+$/, '用户名只能包含字母、数字和下划线'),
    password: z
      .string()
      .min(1, '请输入密码')
      .min(8, '密码至少8个字符')
      .max(128, '密码不能超过128个字符')
      .regex(/[A-Za-z]/, '密码必须包含字母')
      .regex(/[0-9]/, '密码必须包含数字'),
    confirmPassword: z.string().min(1, '请确认密码'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: '两次输入的密码不一致',
    path: ['confirmPassword'],
  })

export type RegisterFormValues = z.infer<typeof registerSchema>

export const onboardingNameSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, '请输入你的称呼')
    .max(50, '称呼不能超过50个字符'),
})

export type OnboardingNameFormValues = z.infer<typeof onboardingNameSchema>

export const changePasswordSchema = z.object({
  oldPassword: z.string().min(6, '原密码至少6个字符'),
  newPassword: z
    .string()
    .min(8, '新密码至少8个字符')
    .max(100, '新密码不能超过100个字符')
    .regex(/[A-Za-z]/, '新密码需包含字母')
    .regex(/[0-9]/, '新密码需包含数字'),
  confirmPassword: z.string().min(1, '请确认新密码'),
}).refine((data) => data.newPassword === data.confirmPassword, {
  message: '两次输入的密码不一致',
  path: ['confirmPassword'],
})

export type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>

export const createLearnerSchema = z.object({
  realName: z
    .string()
    .min(1, '请输入真实姓名')
    .min(2, '姓名至少2个字符')
    .max(50, '姓名不能超过50个字符'),
  educationLevel: z.string().min(1, '请选择学历'),
  major: z.string().min(1, '请输入专业').max(100, '专业不能超过100个字符'),
  graduationYear: z.coerce
    .number()
    .int('毕业年份必须为整数')
    .min(1990, '毕业年份不能早于1990年')
    .max(2035, '毕业年份不能晚于2035年')
    .optional(),
  currentPosition: z.string().max(100, '职位不能超过100个字符').optional(),
  learningStyle: z.string().optional(),
  preferredDifficulty: z.coerce.number().min(1).max(5).optional(),
  dailyStudyTime: z.coerce.number().min(0).max(24).optional(),
  targetIndustry: z.string().min(1, '请选择目标行业'),
  targetPosition: z.string().max(100, '目标岗位不能超过100个字符').optional(),
  learningGoal: z.string().max(500, '学习目标不能超过500个字符').optional(),
  theoreticalFoundation: z.coerce.number().min(0).max(100).optional(),
  programmingAbility: z.coerce.number().min(0).max(100).optional(),
  algorithmDesign: z.coerce.number().min(0).max(100).optional(),
  systemArchitecture: z.coerce.number().min(0).max(100).optional(),
  dataAnalysis: z.coerce.number().min(0).max(100).optional(),
  engineeringPractice: z.coerce.number().min(0).max(100).optional(),
})

export type CreateLearnerFormValues = z.infer<typeof createLearnerSchema>

export const uploadKnowledgeSchema = z.object({
  title: z
    .string()
    .min(1, '请输入文档标题')
    .min(2, '标题至少2个字符')
    .max(200, '标题不能超过200个字符'),
  industry: z.string().min(1, '请选择所属行业'),
  category: z.string().max(100, '分类不能超过100个字符').optional(),
  source: z.string().max(200, '来源不能超过200个字符').optional(),
  author: z.string().max(100, '作者不能超过100个字符').optional(),
  content: z
    .string()
    .min(1, '请输入文档内容')
    .min(10, '文档内容至少10个字符')
    .max(100000, '文档内容不能超过10万个字符'),
})

export type UploadKnowledgeFormValues = z.infer<typeof uploadKnowledgeSchema>

export const generateResourcesSchema = z.object({
  learnerId: z.coerce.number().int().positive('请选择学习者'),
  targetTopic: z
    .string()
    .min(1, '请输入目标主题')
    .min(2, '主题至少2个字符')
    .max(200, '主题不能超过200个字符'),
  industry: z.string().optional(),
  resourceType: z.string().optional(),
})

export type GenerateResourcesFormValues = z.infer<typeof generateResourcesSchema>

export const searchSchema = z.object({
  query: z
    .string()
    .min(1, '请输入搜索内容')
    .max(500, '搜索内容不能超过500个字符'),
  industry: z.string().optional(),
  topK: z.coerce.number().int().min(1).max(50).optional(),
  minSimilarity: z.coerce.number().min(0).max(1).optional(),
})

export type SearchFormValues = z.infer<typeof searchSchema>
