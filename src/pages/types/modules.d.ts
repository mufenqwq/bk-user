/**
 * 静态资源模块类型声明
 * 用于解决 TypeScript 无法识别 CSS、图片等静态资源导入的问题
 */

// CSS 模块类型声明
declare module '*.css' {
  const content: Record<string, string>;
  export default content;
}

declare module '*.scss' {
  const content: Record<string, string>;
  export default content;
}

declare module '*.less' {
  const content: Record<string, string>;
  export default content;
}

// 图片文件模块类型声明
declare module '*.png' {
  const value: string;
  export default value;
}

declare module '*.jpg' {
  const value: string;
  export default value;
}

declare module '*.jpeg' {
  const value: string;
  export default value;
}

declare module '*.gif' {
  const value: string;
  export default value;
}

declare module '*.svg' {
  const value: string;
  export default value;
}

declare module '*.webp' {
  const value: string;
  export default value;
}

declare module '*.ico' {
  const value: string;
  export default value;
}

// js-cookie 模块类型声明
declare module 'js-cookie' {
  interface CookieAttributes {
    expires?: number | Date;
    path?: string;
    domain?: string;
    secure?: boolean;
    sameSite?: 'strict' | 'lax' | 'none';
  }

  interface CookiesStatic {
    get(name: string): string | undefined;
    set(name: string, value: string | object, options?: CookieAttributes): string | undefined;
  }

  const Cookies: CookiesStatic;
  export default Cookies;
}

// @blueking/sub-saas 模块类型声明（npm 包未发布 typings 目录，此处兜底声明）
declare module '@blueking/sub-saas' {
  import type { Router } from 'vue-router';

  /** 子系统根路径：以 /sub 前缀访问时为 /sub/，否则为 / */
  export const rootPath: string;
  /** 是否处于 iframe 嵌入环境（被主系统以 /sub 路径加载） */
  export const subEnv: boolean;
  /** 子系统路由与主系统联动（postMessage 通信） */
  export function connectToMain(router: Router): void;
}
