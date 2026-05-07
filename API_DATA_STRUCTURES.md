# Trendit API Data Structures Guide

This guide provides a detailed breakdown of the data returned by each endpoint. All successful responses (2xx) follow a standardized wrapper format managed by the `StandardizedJSONRenderer`.

## Standardized Response Wrapper
Every successful API call returns a JSON object in this format:
```json
{
    "status": "success",
    "code": 200,
    "message": "Action completed successfully.",
    "data": { ... } // This contains the actual payload
}
```
*Note: If the view returns a "message" field inside its data, it is moved to the top-level "message" field by the renderer.*

---

## 1. Common Objects

### User Minimal Object
Used in Search, Following, Followers, and Buddy lists.
*   `id` (integer): Unique ID of the user.
*   `username` (string): Unique username.
*   `email` (string): User's email.
*   `first_name` (string): User's first name.
*   `last_name` (string): User's last name.

---

## 2. User Authentication & Management

### Register User (`POST /api/users/register/`)
**Payload (`data`):**
*   `email` (string): The registered email address.

### Verify OTP (`POST /api/users/verify-otp/`)
**Payload (`data`):** Empty `{}`. (Status message is in the `message` field).

### Login (`POST /api/users/login/`)
**Payload (`data`):**
*   `refresh` (string): The JWT refresh token (long-lived).
*   `access` (string): The JWT access token (short-lived).

### Token Refresh (`POST /api/users/token/refresh/`)
**Payload (`data`):**
*   `access` (string): A new JWT access token.

### User Profile (`GET/PUT/PATCH /api/users/profile/`)
**Payload (`data`):**
*   `username` (string): The user's unique username.
*   `phone_number` (string|null): The user's phone number.
*   `email` (string): The user's email address (read-only).
*   `first_name` (string): User's first name.
*   `last_name` (string): User's last name.

### User Search (`GET /api/users/search/`)
**Payload (`data`):** A list of **User Minimal Objects**.

### Forgot Password (`POST /api/users/forgot-password/`)
**Payload (`data`):**
*   `email` (string): The email where the OTP was sent.

### Reset Password (`POST /api/users/reset-password/`)
**Payload (`data`):** Empty `{}`.

---

## 3. Content Management

### Post Object (Used in Feed, Trending, and Create Post)
**Payload (`data`):**
*   `id` (integer): Unique ID of the post.
*   `author` (integer): ID of the user who created the post.
*   `author_username` (string): Username of the author.
*   `category` (integer): ID of the category.
*   `category_name` (string): Name of the category.
*   `media_file` (string): URL to the media stored on Cloudinary.
*   `caption` (string): The text description of the post.
*   `aspect_ratio` (float|null): The width/height ratio of the media file.
*   `status` (string): 'pending', 'active', or 'trending'.
*   `created_at` (string): ISO 8601 timestamp.
*   `avg_rating` (float|null): The average of all ratings (1-5).
*   `vote_count` (integer): Total number of votes received.
*   `sub_posts` (list): A list of **Sub-Post Objects**.

### Sub-Post Object
*   `id` (integer): Unique ID of the sub-post.
*   `parent_post` (integer): ID of the main post this is replying to.
*   `author` (integer): ID of the reply author.
*   `author_username` (string): Username of the reply author.
*   `media_file` (string): URL to the media.
*   `caption` (string): Optional text.
*   `aspect_ratio` (float|null): The width/height ratio of the media file.
*   `created_at` (string): ISO 8601 timestamp.

### Category Object (`GET /api/content/categories/`)
**Payload (`data`):** A list of:
*   `id` (integer): Unique ID.
*   `name` (string): Display name.
*   `slug` (string): URL-friendly name.

---

## 4. Social Interactions

### Follow/Unfollow (`POST/DELETE /api/social/follow/`)
**Payload (`data`):** Empty `{}`.

### Following/Followers List (`GET /api/social/following/`, `GET /api/social/followers/`)
**Payload (`data`):** A list of **User Minimal Objects**.

### Buddy List (Mutual Follows) (`GET /api/social/buddies/`)
**Payload (`data`):** A list of **User Minimal Objects**.

### Close Buddy Request Object (`POST/GET /api/social/close-buddies/request/` etc.)
**Payload (`data`):**
*   `id` (integer): ID of the request.
*   `sender` (integer): ID of the user sending the request.
*   `receiver` (integer): ID of the target user.
*   `sender_details` (User Minimal Object): Details of the sender.
*   `receiver_details` (User Minimal Object): Details of the receiver.
*   `status` (string): 'pending', 'accepted', 'rejected'.
*   `created_at` (string): Timestamp.

### Close Buddy Object (Inner Circle) (`GET /api/social/close-buddies/`)
**Payload (`data`):** A list of:
*   `id` (integer): ID of the relationship.
*   `buddy` (integer): ID of the close buddy.
*   `buddy_details` (User Minimal Object): Details of the close buddy.

### Post Approval Object (`POST /api/social/approve-post/`)
**Payload (`data`):**
*   `id` (integer): ID of the approval record.
*   `post` (integer): ID of the post approved.
*   `buddy` (integer): ID of the buddy who approved it.
*   `approved_at` (string): Timestamp.

### Vote Object (`POST /api/social/vote/`)
**Payload (`data`):**
*   `id` (integer): ID of the vote.
*   `post` (integer): ID of the post voted on.
*   `user` (integer): ID of the voter.
*   `value` (integer): Rating given (1-5).

---

## 5. Core Features

### Notification Object (`GET /api/core/notifications/`)
**Payload (`data`):** A list of:
*   `id` (integer): ID of the notification.
*   `recipient` (integer): ID of the user receiving the notification.
*   `actor` (integer): ID of the user who performed the action.
*   `actor_username` (string): Username of the actor.
*   `verb` (string): Description of the action (e.g., 'followed you').
*   `target` (integer): ID of the object involved (Post, User, etc.).
*   `read_status` (boolean): Whether the user has seen it.
*   `created_at` (string): Timestamp.

### Mark Notification as Read (`PATCH/PUT /api/core/notifications/<id>/read/`)
**Payload (`data`):**
*   `status` (string): "notification marked as read".

### Report Object (`POST /api/core/report/`)
**Payload (`data`):**
*   `id` (integer): ID of the report.
*   `reporter` (integer): ID of the user reporting.
*   `content_type` (integer): ContentType ID of the target.
*   `object_id` (integer): ID of the specific post/content.
*   `reason` (string): The text description of the problem.
*   `status` (string): 'submitted', 'in_review', 'resolved', 'dismissed'.
*   `created_at` (string): Timestamp.

### Cleanup Media (`POST /api/core/cleanup-media/`)
**Payload (`data`):**
*   `posts_cleaned` (integer): Number of expired main posts whose media was deleted.
*   `subposts_cleaned` (integer): Number of expired sub-posts whose media was deleted.
`):**
*   `posts_cleaned` (integer): Number of expired main posts whose media was deleted.
*   `subposts_cleaned` (integer): Number of expired sub-posts whose media was deleted.
