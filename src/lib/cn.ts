import { clsx, type ClassValue } from 'clsx'

/**
 * 合并 classnames，兼容 clsx 的所有参数形式。
 * 注：未引入 tailwind-merge 以避免新增依赖；
 * 如未来需要去重冲突的 Tailwind 类，可在此处接入 twMerge。
 */
export function cn(...inputs: ClassValue[]): string {
  return clsx(...inputs)
}
