/**
 * API 类型自动生成入口
 *
 * 生成方式：
 *   npm run openapi:gen
 *
 * 该 barrel 从 generated.ts 重新导出 paths/components/operations，
 * 前端代码应从此处导入而非直接引用 generated.ts，便于未来替换生成器。
 */
export type { paths, components, operations, webhooks } from './generated'
export type {
  ApiResponse,
  ApiRequestBody,
  ApiQueryParams,
  ApiPathParams,
  OperationResponse,
  SchemaType,
} from './helpers'
