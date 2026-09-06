# The Narrative of Second Pass Library

Second Pass Library is a small, self-hosted library for a household or another close community. Its structure borrows from a physical library.

A new library begins with a common room. It holds the shared collection and gives readers a place to browse, read, organize books, and keep notes.

Librarians care for the collection. They import books, correct metadata, and maintain the catalog. Managers care for the people using it: they manage accounts, participation, and access. The owner is a manager with responsibility for the library itself, including its name, settings, and other managers.

Larger libraries can open more rooms. In the software, these rooms are groups that organize books, readers, and shared shelves. The common room is the default group and follows the same basic rules as other groups. Simple mode shows only that room. Advanced mode lets managers create more.

A curator is a reader trusted to look after one room. Curators can organize that group's books and shelves, but only within the collection they can already see. Responsibility for one group does not grant authority over the rest of the library.

The roles build on one another. Librarians can do what curators do across the library and can also import books and edit metadata. Managers add user management. The owner can appoint or remove managers and change library-wide settings.

Marginalia sits at the center of the project.

Marginalia is a record of someone's experience with a book, not an accessory on a catalog entry. A reading session ties one reader to one book during one period of reading, along with its annotations, bookmarks, progress, and notes.

A reader can have one open session for a book. They can leave it open, close it when they finish that reading, or start over later. A reread creates another session instead of overwriting the first one. Earlier readings remain part of the reader's history.

The reader owns that history. The library stores and organizes it, but readers must be able to bring their Marginalia in and take it with them. Changes in library access should not erase their past reading when the system can preserve it safely.

That requirement shapes Book identity. Each imported EPUB is one fixed asset. Catalog metadata can be corrected, but replacing the file in place would make existing CFI locations unreliable. A corrected, repacked, or different edition is therefore imported as a new Book.

The server does not render EPUBs or interpret CFIs. It reads enough metadata to import and catalog an EPUB safely, then treats the file as opaque. The server stores the Book, controls access, and preserves reading sessions and Marginalia.

The separate Second Pass Reader web client handles rendering. It understands EPUB structure, resolves CFIs, displays the Book, and works with the reader's active session and annotations. Keeping EPUB rendering there prevents the rest of the system from depending directly on the rendering library.

The Reader can also translate annotations from other reading systems because it understands the actual EPUB. It can compare foreign locations with the Book, convert them to Second Pass Library's Marginalia format, and send the result to the server. The server does not need to know how each outside reader represents EPUB locations.

The same division of responsibility appears throughout both applications. The SDK handles server communication. Orchestrators coordinate pages and workflows. Page regions assemble focused components. Components display data and report user actions. Shared code moves upward only when more than one real caller needs it.

Second Pass Library is built to preserve a reader's ongoing relationship with a book. Books remain stable, reading experiences accumulate, and the notes in the margins continue to belong to the reader.
