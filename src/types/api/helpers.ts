/**
 * OpenAPI 类型安全辅助工具
 *
 * 从生成的 paths 类型中提取请求参数、响应体、路径参数等，
 * 供 API 层和组件层使用，实现端到端类型安全。
 */
import type { paths, operations } from './generated'

/** 提取指定路径+方法的响应体类型 */
export type ApiResponse<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends { responses: { [K: string]: { content: { 'application/json': infer R } } } }
    ? R
    : never

/** 提取指定路径+方法的请求体类型 */
export type ApiRequestBody<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends { requestBody: { content: { 'application/json': infer R } } }
    ? R
    : never

/** 提取指定路径+方法的查询参数类型 */
export type ApiQueryParams<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends { parameters: { query: infer Q } }
    ? Q
    : never

/** 提取指定路径+方法的路径参数类型 */
export type ApiPathParams<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends { parameters: { path: infer P } }
    ? P
    : never

/** 提取指定 operation 的响应体类型 */
export type OperationResponse<Op extends keyof operations> =
  operations[Op] extends { responses: { [K: string]: { content: { 'application/json': infer R } } } }
    ? R
    : never

/** 从 components.schemas 中提取指定模型类型 */
export type SchemaType<Name extends keyof components['schemas']> =
  components['schemas'][Name]

type components = import('./generated').components
