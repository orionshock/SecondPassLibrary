import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect } from "react";

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
  compact = false,
}: {
  id: string;
  value: string;
  onChange: (html: string) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
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

  return <div className={`limited-rich-text-editor${compact ? " limited-rich-text-editor--compact" : ""}`}>
    <div className="limited-rich-text-editor__toolbar" role="toolbar" aria-label="Text formatting">
      {controls.map((control) => <button
        key={control.name}
        type="button"
        className="limited-rich-text-editor__control"
        aria-label={control.label}
        title={control.label}
        aria-pressed={editor?.isActive(control.name) ?? false}
        disabled={disabled || !editor}
        onClick={control.run}
      ><MaterialIcon name={control.icon} /></button>)}
      <span className="limited-rich-text-editor__separator" aria-hidden="true" />
      <button type="button" className="limited-rich-text-editor__control" aria-label="Undo" title="Undo" disabled={disabled || !editor?.can().undo()} onClick={() => editor?.chain().focus().undo().run()}><MaterialIcon name="undo" /></button>
      <button type="button" className="limited-rich-text-editor__control" aria-label="Redo" title="Redo" disabled={disabled || !editor?.can().redo()} onClick={() => editor?.chain().focus().redo().run()}><MaterialIcon name="redo" /></button>
    </div>
    <EditorContent editor={editor} />
  </div>;
}
