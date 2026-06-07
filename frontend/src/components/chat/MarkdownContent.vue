<script setup lang="ts">
/**
 * MarkdownContent — 安全的 Markdown 渲染组件。
 *
 * 使用 marked 将 Markdown 文本转为 HTML，带代码块样式。
 * 用作 AI 消息内容的渲染器。
 */
import { computed } from 'vue'
import { marked } from 'marked'
import markedKatex from 'marked-katex-extension'
import 'katex/dist/katex.min.css'

// 配置 marked：只允许安全的渲染选项
marked.setOptions({
  breaks: true,       // 支持 GFM 换行
  gfm: true,          // GitHub Flavored Markdown
})
marked.use(markedKatex({
  throwOnError: false,
  nonStandard: true,
}))

const props = defineProps<{
  content: string
}>()

const html = computed(() => {
  if (!props.content) return ''
  try {
    return marked.parse(props.content) as string
  } catch {
    // 解析失败时回退到纯文本
    return escapeHtml(props.content)
  }
})

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
</script>

<template>
  <div
    class="markdown-content prose prose-sm max-w-none dark:prose-invert overflow-x-auto"
    v-html="html"
  />
</template>

<style scoped>
/* ── Markdown 基础样式 ─────────────────────────────────────────────── */

.markdown-content :deep(p) {
  margin-bottom: 0.5em;
}

.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 1.5em;
  margin-bottom: 0.5em;
}

.markdown-content :deep(li) {
  margin-bottom: 0.25em;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  font-weight: 600;
  margin-top: 1em;
  margin-bottom: 0.5em;
  line-height: 1.3;
}

.markdown-content :deep(h1) { font-size: 1.4em; }
.markdown-content :deep(h2) { font-size: 1.2em; }
.markdown-content :deep(h3) { font-size: 1.1em; }

/* ── 代码块 ────────────────────────────────────────────────────────── */

.markdown-content :deep(code) {
  background: rgb(243 244 246);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.875em;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.dark .markdown-content :deep(code) {
  background: rgb(55 65 81);
}

.markdown-content :deep(pre) {
  background: rgb(30 41 59);
  color: rgb(226 232 240);
  padding: 1em;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0.75em 0;
  font-size: 0.85em;
  line-height: 1.5;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-size: inherit;
}

/* ── 表格 ──────────────────────────────────────────────────────────── */

.markdown-content :deep(table) {
  width: 100%;
  display: block;
  border-collapse: collapse;
  overflow-x: auto;
  margin: 0.75em 0;
  font-size: 0.875em;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid rgb(209 213 219);
  padding: 0.4em 0.75em;
  text-align: left;
}

.dark .markdown-content :deep(th),
.dark .markdown-content :deep(td) {
  border-color: rgb(75 85 99);
}

.markdown-content :deep(th) {
  background: rgb(243 244 246);
  font-weight: 600;
}

.dark .markdown-content :deep(th) {
  background: rgb(55 65 81);
}

/* ── 引用块 ────────────────────────────────────────────────────────── */

.markdown-content :deep(blockquote) {
  border-left: 3px solid rgb(59 130 246);
  padding: 0.25em 0.75em;
  margin: 0.5em 0;
  color: rgb(75 85 99);
  background: rgb(249 250 251);
  border-radius: 0 4px 4px 0;
}

.dark .markdown-content :deep(blockquote) {
  border-left-color: rgb(96 165 250);
  color: rgb(156 163 175);
  background: rgb(30 41 59);
}

/* ── 链接 ──────────────────────────────────────────────────────────── */

.markdown-content :deep(a) {
  color: rgb(37 99 235);
  text-decoration: underline;
}

.dark .markdown-content :deep(a) {
  color: rgb(96 165 250);
}

/* ── KaTeX ─────────────────────────────────────────────────────────── */

.markdown-content :deep(.katex-display) {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.25em 0;
}

/* ── 分割线 ────────────────────────────────────────────────────────── */

.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid rgb(209 213 219);
  margin: 1em 0;
}

.dark .markdown-content :deep(hr) {
  border-top-color: rgb(75 85 99);
}
</style>
