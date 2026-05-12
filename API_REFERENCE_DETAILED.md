# Trendit API Detailed Reference

This document provides a definitive guide to all API endpoints, including request methods, payload structures, response formats, and edge cases.

---

## Standardized Response Wrapper
Every successful API call (2xx) returns a JSON object in this format (managed by `StandardizedJSONRenderer`):

```json
{
    "status": "success",
    "code": 200,
    "message": "Action completed successfully.",
    "data": { ... } // Payload
}
```

*   **Errors (4xx, 5xx):** Handled by a custom exception handler.
*   **Standardized messages:** If a view includes a `"message"` field in its response dictionary, it is extracted by the renderer to the top-level `"message"` key.

---

## 1. User Authentication & Management

### Register User
*   **Endpoint:** `POST /api/users/register/`
*   **Auth Required:** No
*   **Payload (JSON):**
    *   `email` (string, required)
    *   `password` (string, required)
    *   `phone_number` (string, optional)
*   **Response (`data`):**
    *   `id` (int)
    *   `email` (string)
    *   `phone_number` (string|null)
*   **Edge Cases:**
    *   If an unverified user exists with the same email/phone, the old account is deleted to allow fresh registration.
    *   If a verified user exists, a `400 Bad Request` is returned with a "user already exists" message.

### Verify OTP
*   **Endpoint:** `POST /api/users/verify-otp/`
*   **Auth Required:** No
*   **Payload (JSON):**
    *   `email` (string, required): Can be email, username, or phone number.
    *   `otp_code` (string, 6 chars, required)
*   **Response (`data`):** Empty `{}`.
*   **Edge Cases:**
    *   Returns `400` if OTP is expired or invalid.

### Login (Obtain Tokens)
*   **Endpoint:** `POST /api/users/login/`
*   **Auth Required:** No
*   **Payload (JSON):**
    *   `username` (string, required): Accepts Email, Username, or Phone Number.
    *   `password` (string, required)
*   **Response (`data`):**
    *   `refresh` (string): JWT refresh token.
    *   `access` (string): JWT access token.
    *   `user_id` (int): ID of the authenticated user.
*   **Edge Cases:**
    *   **Unverified Users:** Returns `401 Unauthorized` with message `ACCOUNT_NOT_VERIFIED` and sends a new OTP.
    *   **Banned Users:** Returns `401 Unauthorized` with the ban reason.

### Token Refresh
*   **Endpoint:** `POST /api/users/token/refresh/`
*   **Payload (JSON):**
    *   `refresh` (string, required)
*   **Response (`data`):**
    *   `access` (string): New access token.

---

## 2. Profile & Search

### Get/Update Profile
*   **Endpoint:** `GET/PUT/PATCH /api/users/profile/`
*   **Auth Required:** Yes
*   **Payload (PUT/PATCH):** `username`, `phone_number`, `first_name`, `last_name`, `profile_picture`.
*   **Response (`data`):** Full profile object including `email` (read-only).

### User Search
*   **Endpoint:** `GET /api/users/search/`
*   **Query Params:** `q` (string, required)
*   **Response (`data`):** List of minimal user objects:
    ```json
    { "id": 1, "username": "...", "email": "...", "first_name": "...", "last_name": "..." }
    ```

---

## 3. Content Management (Posts)

### Post Object Structure (Standardized)
Used in Feed, Trending, Detail, and User Posts responses.
*   `id` (int)
*   `author` (int): User ID.
*   `author_username` (string)
*   `category` (int): Category ID.
*   `category_name` (string)
*   `media_file` (string): Cloudinary URL.
*   `caption` (string)
*   `aspect_ratio` (float|null)
*   `status` (string): 'pending', 'active', 'trending', 'rejected'.
*   `created_at` (string): ISO timestamp.
*   **Annotations (Dynamic):**
    *   `avg_rating` (float|null): 1.0 - 5.0
    *   `vote_count` (int): Total votes.
    *   `favorite_count` (int): Total times favorited.
    *   `user_rating` (int|null): Rating given by the *requesting user*.
    *   `is_favorited` (bool): If the *requesting user* favorited it.

### Create Post
*   **Endpoint:** `POST /api/content/posts/`
*   **Auth Required:** Yes
*   **Format:** `multipart/form-data`
*   **Payload:**
    *   `category` (int, ID)
    *   `media_file` (File)
    *   `caption` (string)
    *   `aspect_ratio` (float, optional)
*   **Edge Cases:** Returns `400` if upload window is closed (based on `AppSettings`).

### Get Feed
*   **Endpoint:** `GET /api/content/feed/`
*   **Auth Required:** No (is_favorited/user_rating will be null/false if anonymous).
*   **Logic:** Returns all posts where `is_media_deleted=False`.

---

## 4. Social Interactions

### Vote on Post
*   **Endpoint:** `POST /api/social/vote/`
*   **Payload (JSON):**
    *   `post` (int, ID)
    *   `value` (int, 1-5)
*   **Response (`data`):** The **Full Post Object** (annotated) + `message`.
*   **Logic:** Create or updates a vote. Updates post `avg_rating` and `vote_count`. Returns updated state for UI sync.

### Favorite Toggle
*   **Endpoint:** `POST /api/social/favorite/`
*   **Payload (JSON):**
    *   `post` (int, ID)
*   **Response (`data`):** The **Full Post Object** (annotated) + `message`.
*   **Logic:** Toggles favorite status. Returns the updated state for UI sync.

### Follow/Unfollow
*   **Endpoint:** `POST/DELETE /api/social/follow/`
*   **Payload (JSON):** `user_id` (int)

### Close Buddy Request
*   **Endpoint:** `POST /api/social/close-buddies/request/`
*   **Payload (JSON):** `receiver` (int, User ID)
*   **Edge Case:** Only **mutual buddies** (users who follow each other) can send these requests.

---

## 5. Notifications & Core

### Notifications
*   **Endpoint:** `GET /api/core/notifications/`
*   **Response (`data`):** List of notification objects.

### Cleanup Media
*   **Endpoint:** `POST /api/core/cleanup-media/`
*   **Auth:** Requires `Authorization: Bearer <CLEANUP_SECRET_TOKEN>`.
*   **Logic:** Deletes Cloudinary media for posts older than 7 days. DB records remain but `is_media_deleted` becomes `true`.
