import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  BookCoverPreview,
  CoverPreviewUrlOwner,
} from "../../../../src/features/library/bookEdit/BookCoverEditor";

function imageFile(name = "cover.png", type = "image/png") {
  return new File(["image"], name, { type });
}

function previewOwner(validate: (url: string) => Promise<boolean> = async () => true) {
  const createObjectURL = vi.fn((file: Blob) => `blob:${(file as File).name}`);
  const revokeObjectURL = vi.fn();
  return {
    createObjectURL,
    revokeObjectURL,
    owner: new CoverPreviewUrlOwner({ createObjectURL, revokeObjectURL }, validate),
  };
}

describe("Book cover replacement preview", () => {
  it("creates and displays an object URL for a valid selected image", async () => {
    const { createObjectURL, owner } = previewOwner();
    const file = imageFile();

    const previewUrl = await owner.select(file);
    const markup = renderToStaticMarkup(<BookCoverPreview
      coverUrl="/media/saved.jpg"
      previewUrl={previewUrl}
      title="Book"
    />);

    expect(createObjectURL).toHaveBeenCalledWith(file);
    expect(markup).toContain('src="blob:cover.png"');
    expect(markup).toContain('role="status"');
    expect(markup).not.toContain('src="/media/saved.jpg"');
  });

  it("revokes the previous URL before replacing the selected file", async () => {
    const { owner, revokeObjectURL } = previewOwner();
    await owner.select(imageFile("first.png"));

    await owner.select(imageFile("second.webp", "image/webp"));

    expect(revokeObjectURL).toHaveBeenCalledWith("blob:first.png");
  });

  it("clears and revokes the local preview so the saved cover is restored", async () => {
    const { owner, revokeObjectURL } = previewOwner();
    await owner.select(imageFile());

    owner.clear();
    const markup = renderToStaticMarkup(<BookCoverPreview coverUrl="/media/saved.jpg" title="Book" />);

    expect(revokeObjectURL).toHaveBeenCalledWith("blob:cover.png");
    expect(markup).toContain('src="/media/saved.jpg"');
    expect(markup).not.toContain('role="status"');
  });

  it("does not replace the saved cover with an invalid selection", async () => {
    const { createObjectURL, owner } = previewOwner();

    const previewUrl = await owner.select(imageFile("cover.txt", "text/plain"));
    const markup = renderToStaticMarkup(<BookCoverPreview
      coverUrl="/media/saved.jpg"
      previewUrl={previewUrl}
      title="Book"
    />);

    expect(createObjectURL).not.toHaveBeenCalled();
    expect(markup).toContain('src="/media/saved.jpg"');
  });

  it("revokes a selected URL when image decoding rejects it", async () => {
    const { owner, revokeObjectURL } = previewOwner(async () => false);

    await expect(owner.select(imageFile())).resolves.toBeUndefined();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:cover.png");
  });

  it("clears the local preview when a successful upload clears the selected file", async () => {
    const { owner, revokeObjectURL } = previewOwner();
    await owner.select(imageFile());

    await owner.select(undefined);

    expect(revokeObjectURL).toHaveBeenCalledWith("blob:cover.png");
  });

  it("revokes the current URL when its owner unmounts", async () => {
    const { owner, revokeObjectURL } = previewOwner();
    await owner.select(imageFile());

    owner.dispose();

    expect(revokeObjectURL).toHaveBeenCalledWith("blob:cover.png");
  });
});

