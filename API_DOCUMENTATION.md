# Trendit API Documentation

This document provides a comprehensive detail of each endpoint provided by the Trendit backend project.

## Table of Contents
1. [User Authentication & Management](#1-user-authentication--management)
2. [Content Management (Posts & Categories)](#2-content-management-posts--categories)
3. [Social Interactions (Follow, Buddy & Close Buddy)](#3-social-interactions-follow-buddy--close-buddy)
4. [Core Features (Notifications & Reporting)](#4-core-features-notifications--reporting)

---

## 1. User Authentication & Management

### Register User
*   **URL:** `/api/users/register/`
*   **Method:** `POST`
*   **Description:** Registers a new user account. A 6-digit OTP is generated and printed to the console for verification.
*   **Input Data (JSON):**
    *   `email` (string, required)
    *   `password` (string, required)
    *   `phone_number` (string, optional)
*   **Success Response:**
    *   **Status Code:** `201 Created`
    *   **Data:** `{"message": "User registered successfully. Please verify your email with the OTP sent.", "email": "user@example.com"}`

### Verify OTP
*   **URL:** `/api/users/verify-otp/`
*   **Method:** `POST`
*   **Description:** Verifies the user's account using the OTP code.
*   **Input Data (JSON):**
    *   `email` (string, required): Can be email, username, or phone number.
    *   `otp_code` (string, 6 characters, required)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"message": "Account verified successfully. You can now login."}`

### Login (Obtain Token)
*   **URL:** `/api/users/login/`
*   **Method:** `POST`
*   **Description:** Authenticates a user and returns JWT access and refresh tokens. Supports login via email, username, or phone number.
*   **Input Data (JSON):**
    *   `username` (string, required): User's identifier (Email, Username, or Phone).
    *   `password` (string, required)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"refresh": "...", "access": "..."}`

### Token Refresh
*   **URL:** `/api/users/token/refresh/`
*   **Method:** `POST`
*   **Input Data (JSON):**
    *   `refresh` (string, required)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"access": "..."}`

### User Profile
*   **URL:** `/api/users/profile/`
*   **Method:** `GET`, `PUT`, `PATCH`
*   **Auth Required:** Yes
*   **Description:** Retrieves or updates the current user's profile.
*   **Input Data (PUT/PATCH JSON):**
*   `username` (string, optional)
*   `phone_number` (string, optional)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"username": "...", "phone_number": "...", "email": "..."}`

### View other User Profile
*   **URL:** `/api/users/profile/<int:user_id>/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Retrieves detailed profile information for a specific user, including followers/following/buddy counts and the current user's relationship status with them.
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:**
        ```json
        {
          "id": 2,
          "username": "other_user",
          "email": "other@example.com",
          "first_name": "John",
          "last_name": "Doe",
          "profile_picture": "http://...",
          "followers_count": 10,
          "following_count": 5,
          "buddies_count": 3,
          "total_posts": 12,
          "is_following": true,
          "is_followed_by": false,
          "is_buddy": false,
          "is_close_buddy": false,
          "close_buddy_request_status": "sent_pending"
        }
        ```

### User Search
*   **URL:** `/api/users/search/` (Also accessible at `/api/social/users/search/`)
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Search users by username, first name, or last name. Returns users along with detailed relationship status relative to the requesting user.
*   **Query Parameters:**
    *   `q` (string, required): Search query.
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** List of user search objects:
        *   `id` (integer)
        *   `username` (string)
        *   `email` (string)
        *   `first_name` (string)
        *   `last_name` (string)
        *   `profile_picture` (string | null)
        *   `is_following` (boolean): `true` if the current user is following this user.
        *   `is_followed_by` (boolean): `true` if this user is following the current user.
        *   `is_buddy` (boolean): `true` if they are mutual buddies.
        *   `is_close_buddy` (boolean): `true` if this user is in the current user's inner circle.
        *   `close_buddy_request_status` (string | null): The state of close buddy requests between both users. Format: `sent_<status>` (e.g. `sent_pending`, `sent_accepted`, `sent_rejected`, `sent_ignored`) or `received_<status>` (e.g. `received_pending`, `received_accepted`, `received_rejected`, `received_ignored`) or `null`.

### Forgot Password Request
*   **URL:** `/api/users/forgot-password/`
*   **Method:** `POST`
*   **Description:** Requests a password reset OTP for a given email.
*   **Input Data (JSON):**
    *   `email` (string, required)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"message": "Password reset OTP sent to email.", "email": "..."}`

### Reset Password
*   **URL:** `/api/users/reset-password/`
*   **Method:** `POST`
*   **Description:** Resets the password using the OTP code received via email.
*   **Input Data (JSON):**
    *   `email` (string, required)
    *   `otp_code` (string, required)
    *   `new_password` (string, required, min 6 characters)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"message": "Password has been reset successfully. You can now login."}`

### Ban User (Admin Only)
*   **URL:** `/api/users/ban/<int:user_id>/`
*   **Method:** `POST`
*   **Auth Required:** Yes (Admin)
*   **Input Data (JSON):**
    *   `ban_reason` (string, optional)

### Unban User (Admin Only)
*   **URL:** `/api/users/unban/<int:user_id>/`
*   **Method:** `POST`
*   **Auth Required:** Yes (Admin)

---

## 2. Content Management (Posts & Categories)

### Create Post
*   **URL:** `/api/content/posts/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Input Data (Multipart/Form-Data):**
    *   `category` (integer, ID, required)
    *   `media_file` (file, required)
    *   `caption` (string, required)
    *   `aspect_ratio` (float, optional): Calculated as width/height on client.

### Edit Post
*   **URL:** `/api/content/posts/<int:post_id>/`
*   **Method:** `PATCH`
*   **Auth Required:** Yes (Author Only)
*   **Input Data (JSON):**
    *   `caption` (string, optional)
    *   `category` (integer, ID, optional)
*   **Description:** Allows the author to update the caption or category of their post.

### Delete Post
*   **URL:** `/api/content/posts/<int:post_id>/`
*   **Method:** `DELETE`
*   **Auth Required:** Yes (Author Only)
*   **Description:** Permanently deletes the post and removes the media file from Cloudinary.

### Get Post Feed
*   **URL:** `/api/content/feed/`
*   **Method:** `GET`
*   **Description:** Returns all posts where media is not deleted, ordered by most recent.

### Get User Posts
*   **URL:** `/api/content/posts/user/<int:user_id>/`
*   **Method:** `GET`
*   **Description:** Returns all posts for a specific user. 
    *   If you are the author, you see all your posts (pending, active, rejected).
    *   If you are viewing someone else's profile, you only see their "Active" or "Trending" posts.
    *   **Note:** This endpoint returns posts even if the media has been deleted (check `is_media_deleted` in response).

### Get Trending Feed
*   **URL:** `/api/content/trending/`
*   **Method:** `GET`
*   **Description:** Returns top "Active" or "Trending" posts ranked by `trending_score`, a confidence-weighted score based on rating quality, vote volume, favorites, recency, a small admin trending-status boost, and category priority (`punished=0.5`, `normal=1.0`, `trending=2.0`).

### Create Sub-Post (Reply)
*   **URL:** `/api/content/subposts/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Input Data (Multipart/Form-Data):**
    *   `parent_post` (integer, ID, required)
    *   `media_file` (file, required)
    *   `caption` (string, optional)
    *   `aspect_ratio` (float, optional): Calculated as width/height on client.

### List Categories
*   **URL:** `/api/content/categories/`
*   **Method:** `GET`
*   **Description:** Returns categories with `priority_status` and computed `priority_multiplier`, both used by the trending algorithm.

---

## 3. Social Interactions (Follow, Buddy & Close Buddy)

### Follow / Unfollow
*   **URL:** `/api/social/follow/`
*   **Method:** `POST`, `DELETE`
*   **Auth Required:** Yes
*   **Description:** `POST` to follow a user, `DELETE` to unfollow. One-way relationship.
*   **Input Data (JSON):**
    *   `user_id` (integer, required): ID of the target user.

### List Following
*   **URL:** `/api/social/following/` or `/api/social/following/<int:user_id>/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists users followed by you (or followed by the specified `user_id`).
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** List of user minimal objects (`id`, `username`, `email`, `first_name`, `last_name`, `profile_picture`).

### List Followers
*   **URL:** `/api/social/followers/` or `/api/social/followers/<int:user_id>/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists users following you (or following the specified `user_id`).
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** List of user minimal objects (`id`, `username`, `email`, `first_name`, `last_name`, `profile_picture`).

### List Buddies (Mutual Follows)
*   **URL:** `/api/social/buddies/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists users with whom you have a mutual follow relationship. **Buddies are created automatically** when two users follow each other.

### Send Close Buddy Request
*   **URL:** `/api/social/close-buddies/request/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** Permission-based request to add a user to your "Inner Circle" (max 5). 
*   **Requirement:** You must be mutual **Buddies** to send a Close Buddy request.
*   **Input Data (JSON):**
    *   `receiver` (integer, User ID, required)

### Respond to Close Buddy Request
*   **URL:** `/api/social/close-buddies/respond/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Input Data (JSON):**
    *   `request_id` (integer, required)
    *   `action` (string: "accepted", "rejected", or "ignored", required)

### List Incoming Close Buddy Requests
*   **URL:** `/api/social/close-buddies/requests/`
*   **Method:** `GET`
*   **Auth Required:** Yes

### List Rejected Close Buddy Requests
*   **URL:** `/api/social/close-buddies/requests/rejected/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists close buddy requests sent to you that you have rejected.

### List Ignored Close Buddy Requests
*   **URL:** `/api/social/close-buddies/requests/ignored/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists close buddy requests sent to you that you have ignored.

### List Pending Sent Close Buddy Requests
*   **URL:** `/api/social/close-buddies/pending-sent/`
*   **Method:** `GET`
*   **Auth Required:** Yes

### List Close Buddies (Inner Circle)
*   **URL:** `/api/social/close-buddies/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists users YOU have added to your inner circle.

### List Users Who Added You as Close Buddy
*   **URL:** `/api/social/close-buddies/added-by/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists users who have added YOU to their inner circle.

### Close Buddy Suggestions
*   **URL:** `/api/social/close-buddies/suggestions/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists mutual buddies who are not currently in your inner circle and don't have pending close buddy requests. Useful for the "Suggestions" section.

### Remove Close Buddy
*   **URL:** `/api/social/close-buddies/remove/`
*   **Method:** `DELETE`
*   **Auth Required:** Yes
*   **Input Data (JSON):**
    *   `user_id` (integer, required)

### List Unapproved Posts from Close Buddies
*   **URL:** `/api/social/close-buddies/unapproved-posts/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists posts from your inner circle that you haven't approved yet.

### Approve Post
*   **URL:** `/api/social/approve-post/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** Allows a close buddy to approve a pending post.
*   **Input Data (JSON):**
    *   `post` (integer, ID, required)

### Vote on Post
*   **URL:** `/api/social/vote/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Input Data (JSON):**
    *   `post` (integer, ID, required)
    *   `value` (integer, 1-5, required)

---

## 4. Core Features (Notifications & Reporting)

### List Notifications
*   **URL:** `/api/core/notifications/`
*   **Method:** `GET`
*   **Auth Required:** Yes

### Mark Notification as Read
*   **URL:** `/api/core/notifications/<int:id>/read/`
*   **Method:** `PATCH` / `PUT`
*   **Auth Required:** Yes

### Report Content
*   **URL:** `/api/core/report/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Input Data (JSON):**
    *   `content_type` (integer, ContentType ID, required)
    *   `object_id` (integer, ID of the post/content, required)
    *   `reason` (string, required)

### Cleanup Expired Media
*   **URL:** `/api/core/cleanup-media/`
*   **Method:** `POST`
*   **Auth Required:** Yes (Secret Token)
*   **Header:** `Authorization: Bearer <CLEANUP_SECRET_TOKEN>`
*   **Description:** Triggers deletion of media files older than 7 days.
