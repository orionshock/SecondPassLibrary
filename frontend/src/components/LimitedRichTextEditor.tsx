import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useState } from "react";

import { MaterialIcon } from "./icons/MaterialIcon";
import "./LimitedRichTextEditor.css";

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
    setShowRaw(true);
  }

  function openRenderedEditor() {
    if (!editor) return;
    editor.commands.setContent(value, { emitUpdate: false });
    const html = editor.isEmpty ? "" : editor.getHTML();
    if (html !== value) onChange(html);
    setShowRaw(false);
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
      <button
        type="button"
        className="limited-rich-text-editor__mode-control"
        disabled={disabled || !editor}
        aria-pressed={showRaw}
        onClick={showRaw ? openRenderedEditor : openRawEditor}
      >{showRaw ? "Show rendered" : "Show raw"}</button>
    </div>
    {showRaw
      ? <textarea
        id={id}
        className="limited-rich-text-editor__raw"
        value={value}
        disabled={disabled}
        maxLength={maxLength}
        spellCheck={false}
        onChange={(event) => onChange(event.target.value)}
      />
      : <EditorContent editor={editor} />}
    {maxLength !== undefined ? <div
      className={`limited-rich-text-editor__count${overLimit ? " limited-rich-text-editor__count--over" : ""}`}
      aria-live="polite"
      title="Stored HTML characters"
    >{value.length} / {maxLength}</div> : null}
  </div>;
}
