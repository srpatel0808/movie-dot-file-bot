"""
Comprehensive Test Suite for MOVIE DOT Telegram Bot.
Validates:
1. New Clean Home Screen (Welcome message & role-based menu)
2. Mandatory Channel Subscription (Force Join) verification flow
3. Instant resume of requested movie upon verification
4. Re-verification before delivering files
5. Quality detection & database multi-file linking (480p, 720p, 1080p, 4K)
6. Duplicate file prevention
7. Admin commands & dynamic channel configuration (/setchannel)
8. Zero-bandwidth file delivery via stored Telegram file_id
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from database import db
import movie_engine
import bot
import admin

def run_movie_dot_tests():
    print("=" * 70)
    print("🎬 RUNNING MOVIE DOT BOT VERIFICATION TEST SUITE")
    print("=" * 70)

    # ----------------------------------------------------
    # TEST 1: New Clean Home Screen & Role-Based Menu
    # ----------------------------------------------------
    print("\n[1/6] Testing Clean Home Screen & Role-Based Navigation...")

    owner_id = 6160210568
    regular_id = 11223344

    # 1. Admin Home Screen
    admin_markup = bot.get_home_markup(owner_id)
    admin_btns = [btn.text for row in admin_markup.inline_keyboard for btn in row]
    assert "🎬 Manage Movies" in admin_btns, "Admin should see Manage Movies button"
    assert "📥 GET ALL FILES" in admin_btns, "Admin should see GET ALL FILES button"
    assert "ℹ️ How to Use" in admin_btns, "Admin should see How to Use button"
    print(f"  ✓ Owner/Admin home menu verified: {admin_btns}")

    # 2. Regular User Home Screen (Admin options must be hidden!)
    user_markup = bot.get_home_markup(regular_id)
    user_btns = [btn.text for row in user_markup.inline_keyboard for btn in row]
    assert "🎬 Manage Movies" not in user_btns, "Regular user MUST NOT see Manage Movies button"
    assert "📥 GET ALL FILES" in user_btns, "Regular user should see GET ALL FILES button"
    assert "ℹ️ How to Use" in user_btns, "Regular user should see How to Use button"
    print(f"  ✓ Regular user home menu verified (admin button hidden): {user_btns}")

    # ----------------------------------------------------
    # TEST 2: Quality Detection & Movie Storage
    # ----------------------------------------------------
    print("\n[2/6] Testing Movie Quality Parsing & Database Storage...")

    movie_id = "test_dot_418_2026"
    db.delete_movie(movie_id)

    movie = db.add_or_update_movie(
        movie_id=movie_id,
        title="418 (2026)",
        year=2026
    )
    assert movie["movie_id"] == movie_id

    # Add 480p, 720p, 1080p
    qualities = [
        ("480p", "fid_480_abc", "uid_480_1", "418.2026.480p.mkv", 400 * 1024 * 1024, False),
        ("720p", "fid_720_def", "uid_720_2", "418.2026.720p.mkv", 900 * 1024 * 1024, False),
        ("1080p", "fid_1080_ghi", "uid_1080_3", "418.2026.1080p.mp4", int(1.7 * 1024 * 1024 * 1024), True)
    ]

    for q, fid, uid, fn, sz, is_v in qualities:
        res = db.add_movie_file(movie_id, fid, uid, fn, sz, q, is_video=is_v)
        assert res["status"] in ["inserted", "updated", "replaced"]

    files = db.get_movie_files(movie_id)
    assert len(files) == 3, f"Expected 3 qualities, got {len(files)}"
    ordered_q = [f["quality"] for f in files]
    assert ordered_q == ["480p", "720p", "1080p"], f"Resolution ordering incorrect: {ordered_q}"
    print(f"  ✓ 3 qualities stored and sorted: {ordered_q}")

    # Test Duplicate Prevention
    res_dup = db.add_movie_file(movie_id, "fid_720_def", "uid_720_2", "418.2026.720p.mkv", 900 * 1024 * 1024, "720p")
    assert res_dup["status"] == "updated"
    assert len(db.get_movie_files(movie_id)) == 3, "Duplicate record created!"
    print("  ✓ Duplicate prevention confirmed: file_unique_id prevented duplicate entry.")

    # ----------------------------------------------------
    # TEST 3: Mandatory Channel Subscription (Force Join)
    # ----------------------------------------------------
    print("\n[3/6] Testing Mandatory Channel Subscription (Force Join)...")

    # Set required subscription channel
    test_channel = "@MovieDotChannel"
    db.set_force_sub_channel(test_channel)
    assert db.get_force_sub_channel() == test_channel
    print(f"  ✓ Set force-join channel to: {test_channel}")

    async def test_force_sub_flow():
        mock_bot = MagicMock()
        mock_user = MagicMock()
        mock_user.id = regular_id
        mock_user.username = "test_viewer"
        mock_user.first_name = "Viewer"

        mock_msg = MagicMock()
        mock_msg.reply_text = AsyncMock()
        mock_update = MagicMock()
        mock_update.effective_user = mock_user
        mock_update.message = mock_msg
        mock_context = MagicMock()
        mock_context.bot = mock_bot
        mock_context.args = [f"get_{movie_id}"]

        # Case A: User has NOT joined the channel
        mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="left"))
        mock_bot.get_chat = AsyncMock(return_value=MagicMock(username="MovieDotChannel", invite_link=None))

        await bot.start_command(mock_update, mock_context)

        # Verify NO movie files or quality buttons were sent!
        assert mock_msg.reply_text.called
        call_text = mock_msg.reply_text.call_args[0][0]
        call_markup = mock_msg.reply_text.call_args[1]["reply_markup"]

        assert "🎬 *Welcome to MOVIE DOT!*" in call_text
        assert "⚠️ *Before accessing movie files, you must subscribe to our Telegram channel.*" in call_text
        # Verify buttons
        btn_texts = [b.text for row in call_markup.inline_keyboard for b in row]
        assert "📢 JOIN CHANNEL" in btn_texts
        assert "✅ I'VE JOINED – VERIFY" in btn_texts
        # Verify callback preserves movie_id
        verify_cb = call_markup.inline_keyboard[1][0].callback_data
        assert verify_cb == f"verify_sub:{movie_id}"
        print("  ✓ Case A: Non-subscriber was blocked from movie files and shown Force Join message.")

        # Case B: User clicks '✅ I'VE JOINED – VERIFY' while still not joined
        mock_query_unsub = MagicMock()
        mock_query_unsub.data = f"verify_sub:{movie_id}"
        mock_query_unsub.from_user = mock_user
        mock_query_unsub.answer = AsyncMock()
        mock_query_unsub.message = MagicMock()
        mock_query_unsub.message.edit_text = AsyncMock()
        mock_update_query_unsub = MagicMock(callback_query=mock_query_unsub, effective_user=mock_user)

        await bot.handle_callback_router(mock_update_query_unsub, mock_context)
        assert mock_query_unsub.answer.called
        assert "Verification failed" in mock_query_unsub.answer.call_args[0][0]
        print("  ✓ Case B: Failed verification showed alert and did not deliver files.")

        # Case C: User joins channel and clicks '✅ I'VE JOINED – VERIFY'
        mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
        mock_query_sub = MagicMock()
        mock_query_sub.data = f"verify_sub:{movie_id}"
        mock_query_sub.from_user = mock_user
        mock_query_sub.answer = AsyncMock()
        mock_query_sub.message = MagicMock()
        mock_query_sub.message.edit_text = AsyncMock()
        mock_update_query_sub = MagicMock(callback_query=mock_query_sub, effective_user=mock_user)

        await bot.handle_callback_router(mock_update_query_sub, mock_context)
        assert mock_query_sub.answer.called
        assert "Verification successful" in mock_query_sub.answer.call_args[0][0]
        # Verify movie qualities screen rendered immediately without starting over
        assert mock_query_sub.message.edit_text.called
        success_text = mock_query_sub.message.edit_text.call_args[0][0]
        assert "🎬 *418 (2026)*" in success_text
        assert "📥 *Select Your Quality:*" in success_text
        assert "- 480p" in success_text
        assert "- 720p" in success_text
        assert "- 1080p" in success_text
        assert "- 2160p" not in success_text  # 4K was not uploaded, so MUST NOT appear!
        print("  ✓ Case C: Successful verification instantly displayed the requested movie's qualities.")

    asyncio.run(test_force_sub_flow())

    # ----------------------------------------------------
    # TEST 4: Re-verification on File Delivery & Instant Send
    # ----------------------------------------------------
    print("\n[4/6] Testing Re-verification on Delivery & Instant Sending...")

    async def test_delivery_flow():
        mock_bot = MagicMock()
        mock_bot.send_video = AsyncMock()
        mock_bot.send_document = AsyncMock()

        mock_user = MagicMock(id=regular_id)
        mock_query = MagicMock()
        mock_query.from_user = mock_user
        mock_query.answer = AsyncMock()
        mock_query.message.chat_id = 12345678
        mock_query.message.reply_text = AsyncMock()
        mock_context = MagicMock(bot=mock_bot)

        # 1. User is member: delivers 720p
        mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
        await bot.send_movie_file(mock_query, mock_context, movie_id, "720p")

        assert mock_bot.send_document.called
        call_kwargs = mock_bot.send_document.call_args[1]
        assert call_kwargs["document"] == "fid_720_def"
        print(f"  ✓ Delivered 720p file using stored file_id: {call_kwargs['document']}")

        # 2. User left channel right before clicking 1080p
        mock_bot.get_chat_member = AsyncMock(return_value=MagicMock(status="left"))
        mock_bot.send_video.reset_mock()
        await bot.send_movie_file(mock_query, mock_context, movie_id, "1080p")
        assert not mock_bot.send_video.called, "File must not be delivered if user left channel!"
        assert mock_query.message.reply_text.called
        assert "Before accessing movie files" in mock_query.message.reply_text.call_args[0][0]
        print("  ✓ Re-verification blocked delivery when user was no longer in channel.")

    asyncio.run(test_delivery_flow())

    # ----------------------------------------------------
    # TEST 5: Admin Channel Management Commands (/setchannel)
    # ----------------------------------------------------
    print("\n[5/6] Testing Admin Settings & /setchannel Command...")

    async def test_admin_settings():
        mock_admin = MagicMock(id=owner_id)
        mock_msg = MagicMock()
        mock_msg.reply_text = AsyncMock()
        mock_update = MagicMock(effective_user=mock_admin, message=mock_msg)
        mock_ctx = MagicMock()

        # Update channel to @NewMovieChannel
        mock_ctx.args = ["@NewMovieChannel"]
        await admin.handle_set_channel_command(mock_update, mock_ctx)
        assert db.get_force_sub_channel() == "@NewMovieChannel"
        print("  ✓ Admin updated force-join channel to @NewMovieChannel via /setchannel.")

        # Disable force-join
        mock_ctx.args = ["off"]
        await admin.handle_set_channel_command(mock_update, mock_ctx)
        assert db.get_force_sub_channel() == ""
        print("  ✓ Admin disabled force-join via '/setchannel off'.")

        # Restore channel for normal operations
        db.set_force_sub_channel(test_channel)

    asyncio.run(test_admin_settings())

    # ----------------------------------------------------
    # TEST 6: Channel Post Indexing with 'GET ALL FILES' Button
    # ----------------------------------------------------
    print("\n[6/6] Testing Channel Post Auto-Indexing & GET ALL FILES Button...")

    async def test_channel_post_flow():
        mock_bot = MagicMock()
        mock_bot.edit_message_reply_markup = AsyncMock()
        mock_context = MagicMock(bot=mock_bot)

        mock_video = MagicMock(
            file_id="fid_channel_1080",
            file_unique_id="uid_chan_1080",
            file_name="Inception (2010) 1080p.mkv",
            file_size=2 * 1024 * 1024 * 1024,
            mime_type="video/x-matroska",
            width=1920,
            height=1080
        )
        mock_post = MagicMock(
            video=mock_video,
            document=None,
            photo=None,
            caption="🎬 Inception (2010)",
            chat=MagicMock(id=-100987654321),
            message_id=555
        )
        mock_update = MagicMock(channel_post=mock_post)

        await bot.handle_channel_post(mock_update, mock_context)

        # Verify movie was indexed in DB
        inc_movie = db.get_movie("inception_2010")
        assert inc_movie is not None
        assert inc_movie["title"] == "Inception (2010)"
        inc_files = db.get_movie_files("inception_2010")
        assert len(inc_files) == 1
        assert inc_files[0]["quality"] == "1080p"

        # Verify '📥 GET ALL FILES' inline button was attached
        assert mock_bot.edit_message_reply_markup.called
        markup_call = mock_bot.edit_message_reply_markup.call_args[1]["reply_markup"]
        btn = markup_call.inline_keyboard[0][0]
        assert btn.text == "📥 GET ALL FILES"
        assert "start=get_inception_2010" in btn.url
        print(f"  ✓ Channel post auto-indexed 'Inception (2010)' and attached '{btn.text}' button ({btn.url}).")

        # Cleanup test movie
        db.delete_movie("inception_2010")

    asyncio.run(test_channel_post_flow())

    # Cleanup test movie
    db.delete_movie(movie_id)

    print("\n" + "=" * 70)
    print("🎉 ALL MOVIE DOT BOT TESTS PASSED WITH 100% SUCCESS!")
    print("======================================================================")

if __name__ == "__main__":
    run_movie_dot_tests()
