import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef, useState } from "react";

import { MaterialIcon } from "./icons/MaterialIcon";
import "./LimitedRichTextEditor.css";

export const DESCRIPTIVE_PROSE_MAX_LENGTH = 25_000;
const RAW_HISTORY_LIMIT = 100;

const extensions = [StarterKit.configure({
  blockquote: false,
  code: false,
  codeBlock: false,
  heading: false,
  horizontalRule: false,
  link: false,
  strike: false,
  underline: false,
})];

export function LimitedRichTextEditor({
  id,
  value,
  onChange,
  disabled = false,
  maxLength,
}: {
  id: string;
  value: string;
  onChange: (html: string) => void;
  disabled?: boolean;
  maxLength?: number;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const rawEditorRef = useRef<HTMLTextAreaElement>(null);
  const rawUndoStack = useRef<string[]>([]);
  const rawRedoStack = useRef<string[]>([]);
  const editor = useEditor({
    extensions,
    content: value,
    editable: !disabled,
    immediatelyRender: false,
    shouldRerenderOnTransaction: true,
    editorProps: {
      attributes: {
        id,
        class: "limited-rich-text-editor__content",
      },
    },
    onUpdate: ({ editor: updatedEditor }) => {
      if (!updatedEditor.isFocused) return;
      onChange(updatedEditor.isEmpty ? "" : updatedEditor.getHTML());
    },
  });

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!disabled);
  }, [disabled, editor]);

  useEffect(() => {
    if (!editor) return;
    const current = editor.isEmpty ? "" : editor.getHTML();
    if (current !== value) editor.commands.setContent(value, { emitUpdate: false });
  }, [editor, value]);

  const controls = [
    { name: "bold", icon: "format_bold", label: "Bold", run: () => editor?.chain().focus().toggleBold().run() },
    { name: "italic", icon: "format_italic", label: "Italic", run: () => editor?.chain().focus().toggleItalic().run() },
    { name: "bulletList", icon: "format_list_bulleted", label: "Bulleted list", run: () => editor?.chain().focus().toggleBulletList().run() },
    { name: "orderedList", icon: "format_list_numbered", label: "Numbered list", run: () => editor?.chain().focus().toggleOrderedList().run() },
  ] as const;

  function openRawEditor() {
    if (!editor) return;
    const html = editor.isEmpty ? "" : editor.getHTML();
    if (html !== value) onChange(html);
    rawUndoStack.current = [];
    rawRedoStack.current = [];
    setShowRaw(true);
  }

  function openRenderedEditor() {
    if (!editor) return;
    editor.commands.setContent(value, { emitUpdate: false });
    const html = editor.isEmpty ? "" : editor.getHTML();
    if (html !== value) onChange(html);
    setShowRaw(false);
  }

  function focusRawEditor(cursor: number) {
    requestAnimationFrame(() => {
      rawEditorRef.current?.focus();
      rawEditorRef.current?.setSelectionRange(cursor, cursor);
    });
  }

  function commitRawValue(nextValue: string) {
    if (nextValue === value) return false;
    if (maxLength !== undefined && nextValue.length > maxLength) return false;
    rawUndoStack.current.push(value);
    if (rawUndoStack.current.length > RAW_HISTORY_LIMIT) rawUndoStack.current.shift();
    rawRedoStack.current = [];
    onChange(nextValue);
    return true;
  }

  function undoRawChange() {
    const previous = rawUndoStack.current.pop();
    if (previous === undefined) return;
    rawRedoStack.current.push(value);
    onChange(previous);
    focusRawEditor(previous.length);
  }

  function redoRawChange() {
    const next = rawRedoStack.current.pop();
    if (next === undefined) return;
    rawUndoStack.current.push(value);
    onChange(next);
    focusRawEditor(next.length);
  }

  function replaceRawRange(
    rangeStart: number,
    rangeEnd: number,
    replacement: string,
    selectionStart: number,
    selectionEnd = selectionStart,
  ) {
    const nextValue = `${value.slice(0, rangeStart)}${replacement}${value.slice(rangeEnd)}`;
    if (!commitRawValue(nextValue)) return;
    requestAnimationFrame(() => {
      rawEditorRef.current?.focus();
      rawEditorRef.current?.setSelectionRange(selectionStart, selectionEnd);
    });
  }

  function wrapRawSelection(tag: "p" | "b" | "i") {
    const rawEditor = rawEditorRef.current;
    if (!rawEditor) return;
    const { selectionStart: start, selectionEnd: end } = rawEditor;
    const opening = `<${tag}>`;
    const selected = value.slice(start, end);
    const replacement = `${opening}${selected}</${tag}>`;
    replaceRawRange(
      start,
      end,
      replacement,
      start + opening.length,
      end + opening.length,
    );
  }

  function insertRawBreak() {
    const rawEditor = rawEditorRef.current;
    if (!rawEditor) return;
    const { selectionStart: start, selectionEnd: end } = rawEditor;
    replaceRawRange(start, end, "<br>", start + 4);
  }

  function wrapRawListItem() {
    const rawEditor = rawEditorRef.current;
    if (!rawEditor) return;
    let { selectionStart: start, selectionEnd: end } = rawEditor;
    if (start === end) {
      start = value.lastIndexOf("\n", start - 1) + 1;
      const nextLine = value.indexOf("\n", end);
      end = nextLine === -1 ? value.length : nextLine;
    }
    const selected = value.slice(start, end);
    const replacement = `<li>${selected}</li>`;
    replaceRawRange(start, end, replacement, start + 4, end + 4);
  }

  function wrapRawList(tag: "ul" | "ol") {
    const rawEditor = rawEditorRef.current;
    if (!rawEditor) return;
    const { selectionStart: start, selectionEnd: end } = rawEditor;
    const selected = value.slice(start, end);
    const items = selected
      ? selected.split(/\r?\n/).map((line) => `<li>${line}</li>`).join("")
      : "<li></li>";
    const opening = `<${tag}>`;
    const replacement = `${opening}${items}</${tag}>`;
    const contentStart = start + opening.length + 4;
    const contentEnd = start + opening.length + items.length - 5;
    replaceRawRange(
      start,
      end,
      replacement,
      contentStart,
      selected ? contentEnd : contentStart,
    );
  }

  const overLimit = maxLength !== undefined && value.length > maxLength;

  return <div className="limited-rich-text-editor">
    <div className="limited-rich-text-editor__toolbar" role="toolbar" aria-label="Text formatting">
      {!showRaw ? controls.map((control) => <button
        key={control.name}
        type="button"
        className="limited-rich-text-editor__control"
        aria-label={control.label}
        title={control.label}
        aria-pressed={editor?.isActive(control.name) ?? false}
        disabled={disabled || !editor}
        onClick={control.run}
      ><MaterialIcon name={control.icon} /></button>) : null}
      {!showRaw ? <>
        <span className="limited-rich-text-editor__separator" aria-hidden="true" />
        <button type="button" className="limited-rich-text-editor__control" aria-label="Undo" title="Undo" disabled={disabled || !editor?.can().undo()} onClick={() => editor?.chain().focus().undo().run()}><MaterialIcon name="undo" /></button>
        <button type="button" className="limited-rich-text-editor__control" aria-label="Redo" title="Redo" disabled={disabled || !editor?.can().redo()} onClick={() => editor?.chain().focus().redo().run()}><MaterialIcon name="redo" /></button>
      </> : null}
      {showRaw ? <div className="limited-rich-text-editor__raw-controls" role="group" aria-label="Supported HTML tags">
        <button type="button" disabled={disabled} onClick={() => wrapRawSelection("p")}>{"<p>"}</button>
        <button type="button" disabled={disabled} onClick={insertRawBreak}>{"<br>"}</button>
        <button type="button" disabled={disabled} onClick={() => wrapRawSelection("b")}>{"<b>"}</button>
        <button type="button" disabled={disabled} onClick={() => wrapRawSelection("i")}>{"<i>"}</button>
        <button type="button" disabled={disabled} onClick={() => wrapRawList("ul")}>{"<ul>"}</button>
        <button type="button" disabled={disabled} onClick={() => wrapRawList("ol")}>{"<ol>"}</button>
        <button type="button" disabled={disabled} onClick={wrapRawListItem}>{"<li>"}</button>
      </div> : null}
      {showRaw ? <>
        <span className="limited-rich-text-editor__separator" aria-hidden="true" />
        <button type="button" className="limited-rich-text-editor__control" aria-label="Undo" title="Undo" disabled={disabled || rawUndoStack.current.length === 0} onClick={undoRawChange}><MaterialIcon name="undo" /></button>
        <button type="button" className="limited-rich-text-editor__control" aria-label="Redo" title="Redo" disabled={disabled || rawRedoStack.current.length === 0} onClick={redoRawChange}><MaterialIcon name="redo" /></button>
      </> : null}
      <button
        type="button"
        className="limited-rich-text-editor__mode-control"
        disabled={disabled || !editor}
        aria-pressed={showRaw}
        onClick={showRaw ? openRenderedEditor : openRawEditor}
      >{showRaw ? "Show rendered" : "Show raw"}</button>
    </div>
    <div className="limited-rich-text-editor__body">
      {showRaw
        ? <textarea
          ref={rawEditorRef}
          id={id}
          className="limited-rich-text-editor__raw"
          value={value}
          disabled={disabled}
          maxLength={maxLength}
          spellCheck={false}
          onChange={(event) => commitRawValue(event.target.value)}
        />
        : <EditorContent className="limited-rich-text-editor__rendered" editor={editor} />}
    </div>
    {maxLength !== undefined ? <div
      className={`limited-rich-text-editor__count${overLimit ? " limited-rich-text-editor__count--over" : ""}`}
      aria-live="polite"
      title="Stored HTML characters"
    >
      <span>{showRaw
        ? "Only supported tags are retained."
        : "Formatting counts toward the character limit."}</span>
      <span>{value.length.toLocaleString("en-US")} / {maxLength.toLocaleString("en-US")}</span>
    </div> : null}
  </div>;
}
