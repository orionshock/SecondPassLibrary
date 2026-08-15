export interface LibraryGroupResponse {
  id: string;
  name: string;
  description: string;
  is_public_group: boolean;
  preview_books?: Array<{ id: string; title: string; cover_url: string | null }>;
}

export interface GroupMembershipResponse {
  user: { profile_id: string; username: string };
  is_curator: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface BookGroupAssignmentResponse { id: string; group_id: string; book_id: string; }
