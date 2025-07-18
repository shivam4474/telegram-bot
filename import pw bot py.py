import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from sqlalchemy import create_engine, Column, String, Integer, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session as SQLAlchemySession
from sqlalchemy.exc import SQLAlchemyError

# =============================================================================
# 1. SETUP LOGGING
# =============================================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# =============================================================================
# 2. CONFIGURATION
# =============================================================================
# IMPORTANT: Replace with your actual bot token
TOKEN = "8146817570:AAH6k5ZcmTGYJlFEfx7PxhZeDSj5dl6lRHs" 
OWNER_ID = 549086084
VERIFICATION_GROUP_ID = -1001219085941
MAIN_GROUP_LINK = "https://t.me/+4Yc9OHxB87NlOTNl"


# =============================================================================
# 3. DATABASE SETUP
# =============================================================================
Base = declarative_base()

class Admin(Base):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=True)
    username = Column(String, unique=True, nullable=False)
    crypto_address = Column(String, nullable=True)
    upi_id = Column(String, nullable=True)
    is_super_admin = Column(Boolean, default=False)

try:
    engine = create_engine('sqlite:///payment_verification.db', pool_pre_ping=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    logger.info("Database connection established and tables are ready.")
except Exception as e:
    logger.critical(f"FATAL: Could not connect to the database. Exiting. Error: {e}")
    exit()


# =============================================================================
# 4. UTILITY FUNCTIONS
# =============================================================================
def setup_owner():
    """Initializes or verifies the owner in the database as a super admin."""
    session = Session()
    try:
        owner = session.query(Admin).filter(Admin.user_id == OWNER_ID).first()
        if not owner:
            placeholder_username = f"owner_placeholder_{OWNER_ID}"
            if not session.query(Admin).filter(Admin.username == placeholder_username).first():
                owner = Admin(user_id=OWNER_ID, username=placeholder_username, is_super_admin=True)
                session.add(owner)
                session.commit()
                logger.info(f"Owner {OWNER_ID} added to the database as super admin.")
        elif not owner.is_super_admin:
            owner.is_super_admin = True
            session.commit()
            logger.info(f"Owner {OWNER_ID}'s super admin status was restored.")
    except SQLAlchemyError as e:
        logger.error(f"Database error during owner setup: {e}")
        session.rollback()
    finally:
        session.close()

def is_super_admin(user_id: int, session: SQLAlchemySession) -> bool:
    """Checks if a user is a super admin."""
    admin = session.query(Admin).filter(Admin.user_id == user_id, Admin.is_super_admin == True).first()
    return bool(admin)


# =============================================================================
# 5. BOT COMMAND HANDLERS
# =============================================================================

# --- Core Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command with tailored responses."""
    user = update.effective_user
    chat = update.effective_chat
    session = Session()

    try:
        if chat.type == "private":
            # Link admin accounts when they first DM the bot
            if user.username:
                admin_by_username = session.query(Admin).filter(Admin.username == user.username, Admin.user_id == None).first()
                if admin_by_username:
                    admin_by_username.user_id = user.id
                    session.commit()
                    logger.info(f"Linked user_id {user.id} to admin @{user.username}")
                    await update.message.reply_text(
                        "🔑 <b>Admin Account Activated!</b>\n\n"
                        f"Welcome, @{user.username}. Your Telegram account is now successfully linked to your admin profile.\n\n"
                        "You can now use your assigned commands. Type /start again to see them.",
                        parse_mode=ParseMode.HTML
                    )
                    return # Stop further execution to show the activation message first

            # Check admin status after potential linking
            admin_record = session.query(Admin).filter(Admin.user_id == user.id).first()
            
            if admin_record:
                if admin_record.is_super_admin:
                    welcome_msg = (
                        "👑 <b>SUPER ADMIN DASHBOARD</b> 👑\n\n"
                        "Welcome! You have full administrative privileges. Here are your commands:\n\n"
                        "<b>Management:</b>\n"
                        "➤ /add_admin <code>@username</code>\n"
                        "➤ /remove_admin <code>@username</code>\n"
                        "➤ /promote <code>@username</code>\n"
                        "➤ /demote <code>@username</code>\n"
                        "➤ /admins - View all admins\n\n"
                        "<b>Payment Details:</b>\n"
                        "➤ /setadmin_crypto <code>@username ADDRESS</code>\n"
                        "➤ /setadmin_upi <code>@username UPI_ID</code>"
                    )
                else:
                    welcome_msg = (
                        "🛡️ <b>ADMIN DASHBOARD</b> 🛡️\n\n"
                        "Welcome, Admin. Here are your available commands:\n\n"
                        "➤ /admins - View the list of all admins."
                    )
                await update.message.reply_text(welcome_msg, parse_mode=ParseMode.HTML)
            else:
                # Welcome message for regular users
                join_button = InlineKeyboardButton(
                    "🌍 Join Pagal World 🌍", 
                    url=MAIN_GROUP_LINK
                )
                keyboard = [[join_button]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                welcome_msg = (
                    "🛡️ <b>Welcome to the Verification Bot!</b> 🛡️\n\n"
                    "I am here to help you perform safe and secure transactions within our community.\n\n"
                    "In our main group, you can use the /verify command to check if a Crypto Address or UPI ID belongs to one of our trusted admins.\n\n"
                    "Click the button below to join our main group!"
                )
                await update.message.reply_text(
                    welcome_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
        else:
            # Message for /start in the group
            group_msg = (
                "🔐 <b>Pagal World Verification Bot</b>\n\n"
                "I'm active and ready to protect you from scams!\n\n"
                "➡️ Use <code>/verify [address or UPI]</code> to check a payment detail."
            )
            await update.message.reply_text(group_msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error("Critical error in /start command: %s", e, exc_info=True)
        await update.message.reply_text("⚙️ An unexpected error occurred. Please try again later.")
    finally:
        session.close()

# --- Admin-Only Commands (Private Chat) ---
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a formatted list of all registered admins."""
    session = Session()
    try:
        admins = session.query(Admin).order_by(Admin.is_super_admin.desc(), Admin.username).all()
        if not admins:
            await update.message.reply_text("텅 No admins are currently registered in the database.")
            return
            
        admin_list = ["👥 <b>Registered Admin Team</b> 👥\n"]
        for admin in admins:
            role = "👑 Super Admin" if admin.is_super_admin else "🛡️ Admin"
            status_icon = "✅" if admin.user_id else "⚠️"
            methods = []
            if admin.crypto_address: methods.append("💰")
            if admin.upi_id: methods.append("💳")
            method_icons = " ".join(methods) if methods else "None"
            
            admin_list.append(
                f"\n• <b>@{admin.username}</b>\n"
                f"  Status: {role}\n"
                f"  Account Linked: {status_icon}\n"
                f"  Payment Methods: {method_icons}"
            )
        
        admin_list.append(
            "\n\n— — — — — — — — — —\n"
            "<b>Key:</b>\n"
            "✅ - Account linked to the bot.\n"
            "⚠️ - Admin added, but needs to /start the bot.\n"
            "💰 - Crypto Address is set.\n"
            "💳 - UPI ID is set."
        )
            
        await update.message.reply_text("\n".join(admin_list), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error("Error in /admins command: %s", e, exc_info=True)
        await update.message.reply_text("⚙️ An error occurred while fetching the admin list.")
    finally:
        session.close()

# --- Group Commands ---
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks a crypto address or UPI ID against the admin database."""
    session = Session()
    try:
        if not context.args:
            await update.message.reply_text(
                "ℹ️ <b>How to Verify</b>\n\n"
                "Please provide an address or UPI ID to check.\n\n"
                "<b>Example:</b>\n"
                "<code>/verify YourCryptoAddressHere</code>\n"
                "<code>/verify your-upi@id</code>",
                parse_mode=ParseMode.HTML
            )
            return

        address_to_check = ' '.join(context.args)

        admin_found = session.query(Admin).filter(
            (Admin.crypto_address == address_to_check) | (Admin.upi_id == address_to_check)
        ).first()

        if admin_found:
            role_emoji = "👑" if admin_found.is_super_admin else "🛡️"
            message = (
                "✅ <b>VERIFIED & TRUSTED</b> ✅\n\n"
                "This payment detail is confirmed and secure.\n\n"
                "<b>Address/ID:</b>\n"
                f"<code>{address_to_check}</code>\n\n"
                "It belongs to our trusted admin:\n"
                f"➡️ <b>@{admin_found.username}</b> {role_emoji}"
            )
        else:
            message = (
                "🚨 <b>WARNING: UNVERIFIED</b> 🚨\n\n"
                "This payment detail was <b>NOT FOUND</b> in our secure database.\n\n"
                "<b>Address/ID Checked:</b>\n"
                f"<code>{address_to_check}</code>\n\n"
                "🔴 <b>DO NOT SEND FUNDS.</b> This is a high-risk transaction and could be a scam."
            )
        
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error("Error in /verify command: %s", e, exc_info=True)
        await update.message.reply_text("⚙️ An error occurred during verification. Please try again.")
    finally:
        session.close()


# =============================================================================
# 6. ADMIN MANAGEMENT COMMANDS (Private, Super Admin Only)
# =============================================================================
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = Session()
    try:
        if not is_super_admin(user_id, session):
            await update.message.reply_text("🚫 <b>Access Denied</b>\nThis command is for Super Admins only.")
            return
        if not context.args:
            await update.message.reply_text("ℹ️ <b>Usage:</b> <code>/add_admin @username</code>")
            return
        new_username = context.args[0].lstrip('@')
        if session.query(Admin).filter(Admin.username == new_username).first():
            await update.message.reply_text(f"⚠️ <b>Already Exists</b>\n@{new_username} is already on the admin list.")
            return
        new_admin = Admin(username=new_username)
        session.add(new_admin)
        session.commit()
        await update.message.reply_text(
            f"✅ <b>Admin Added</b>\n\n`@{new_username}` is now a regular admin.\n\n"
            "<b>Action Required:</b> They must start a private chat with me (/start) to link their account and receive commands.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error("Error in /add_admin: %s", e, exc_info=True)
        await update.message.reply_text("⚙️ An error occurred while adding the admin.")
    finally:
        session.close()

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = Session()
    try:
        if not is_super_admin(user_id, session): 
            await update.message.reply_text("🚫 <b>Access Denied</b>\nThis command is for Super Admins only.")
            return
        if not context.args:
            await update.message.reply_text("ℹ️ <b>Usage:</b> <code>/remove_admin @username</code>")
            return
        target_username = context.args[0].lstrip('@')
        target_admin = session.query(Admin).filter(Admin.username == target_username).first()
        if not target_admin:
            await update.message.reply_text(f"❓ <b>Admin Not Found</b>\nThe username @{target_username} is not in our database.")
            return
        if target_admin.user_id == OWNER_ID:
            await update.message.reply_text("🛡️ <b>Action Blocked</b>\nThe bot owner cannot be removed.")
            return
        session.delete(target_admin)
        session.commit()
        await update.message.reply_text(f"🗑️ <b>Admin Removed</b>\n\n@{target_username} has been successfully removed from the admin list.")
    except Exception as e:
        logger.error("Error in /remove_admin: %s", e, exc_info=True)
        await update.message.reply_text("⚙️ Failed to remove admin due to an internal error.")
    finally:
        session.close()

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = Session()
    try:
        if not is_super_admin(user_id, session): 
            await update.message.reply_text("🚫 <b>Access Denied</b>\nThis command is for Super Admins only.")
            return
        if not context.args:
            await update.message.reply_text("ℹ️ <b>Usage:</b> <code>/promote @username</code>")
            return
        target_username = context.args[0].lstrip('@')
        target_admin = session.query(Admin).filter(Admin.username == target_username).first()
        if not target_admin:
            await update.message.reply_text(f"❓ <b>Admin Not Found</b>\nThe username @{target_username} is not in our database.")
            return
        if target_admin.is_super_admin:
            await update.message.reply_text(f"⚠️ <b>No Change</b>\n@{target_username} is already a Super Admin.")
            return
        target_admin.is_super_admin = True
        session.commit()
        await update.message.reply_text(f"🚀 <b>Promotion Successful</b>\n\n@{target_username} has been promoted to <b>Super Admin</b>.")
    except Exception as e:
        logger.error("Error in /promote: %s", e, exc_info=True)
        await update.message.reply_text("⚙️ Failed to promote admin due to an internal error.")
    finally:
        session.close()

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = Session()
    try:
        if not is_super_admin(user_id, session): 
            await update.message.reply_text("🚫 <b>Access Denied</b>\nThis command is for Super Admins only.")
            return
        if not context.args:
            await update.message.reply_text("ℹ️ <b>Usage:</b> <code>/demote @username</code>")
            return
        target_username = context.args[0].lstrip('@')
        target_admin = session.query(Admin).filter(Admin.username == target_username).first()
        if not target_admin:
            await update.message.reply_text(f"❓ <b>Admin Not Found</b>\nThe username @{target_username} is not in our database.")
            return
        if target_admin.user_id == OWNER_ID:
            await update.message.reply_text("🛡️ <b>Action Blocked</b>\nThe bot owner cannot be demoted.")
            return
        if not target_admin.is_super_admin:
            await update.message.reply_text(f"⚠️ <b>No Change</b>\n@{target_username} is already a regular Admin.")
            return
        target_admin.is_super_admin = False
        session.commit()
        await update.message.reply_text(f"📉 <b>Demotion Successful</b>\n\n@{target_username} has been demoted to a regular <b>Admin</b>.")
    except Exception as e:
        logger.error("Error in /demote: %s", e, exc_info=True)
        await update.message.reply_text("⚙️ Failed to demote admin due to an internal error.")
    finally:
        session.close()

async def set_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
    user_id = update.effective_user.id
    session = Session()
    try:
        if not is_super_admin(user_id, session): 
            await update.message.reply_text("🚫 <b>Access Denied</b>\nThis command is for Super Admins only.")
            return
        if len(context.args) < 2:
            await update.message.reply_text(f"ℹ️ <b>Usage:</b> <code>/setadmin_{method} @username VALUE</code>", parse_mode=ParseMode.HTML)
            return
            
        target_username = context.args[0].lstrip('@')
        value = ' '.join(context.args[1:])
        target_admin = session.query(Admin).filter(Admin.username == target_username).first()

        if not target_admin:
            await update.message.reply_text(f"❓ <b>Admin Not Found</b>\nThe username @{target_username} is not in our database.")
            return
        
        method_emoji = "💰" if method == "crypto" else "💳"
        if method == "crypto":
            target_admin.crypto_address = value
        elif method == "upi":
            target_admin.upi_id = value
            
        session.commit()
        await update.message.reply_text(
            f"✅ <b>Payment Info Updated</b>\n\n"
            f"{method_emoji} The {method.upper()} for <b>@{target_username}</b> has been set to:\n"
            f"<code>{value}</code>", 
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in /setadmin_{method}: %s", e, exc_info=True)
        await update.message.reply_text(f"⚙️ Failed to set {method.upper()} details due to an internal error.")
    finally:
        session.close()

async def setadmin_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_payment(update, context, "crypto")

async def setadmin_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_payment(update, context, "upi")

# =============================================================================
# 7. MAIN FUNCTION TO RUN THE BOT
# =============================================================================
def main() -> None:
    """Sets up and runs the Telegram bot."""
    # Ensure owner is in DB at startup
    setup_owner()
    
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(30) # Increased timeouts for stability
        .read_timeout(30)
        .build()
    )
    
    # Define chat filters
    private_filter = filters.ChatType.PRIVATE
    # The group filter ensures these commands only work in your specific group
    group_filter = filters.Chat(chat_id=VERIFICATION_GROUP_ID)
    
    # --- Register Handlers ---
    # Core command available to everyone
    application.add_handler(CommandHandler("start", start))
    
    # Admin commands (private chat only)
    application.add_handler(CommandHandler("admins", list_admins, filters=private_filter))
    application.add_handler(CommandHandler("add_admin", add_admin, filters=private_filter))
    application.add_handler(CommandHandler("remove_admin", remove_admin, filters=private_filter))
    application.add_handler(CommandHandler("promote", promote, filters=private_filter))
    application.add_handler(CommandHandler("demote", demote, filters=private_filter))
    application.add_handler(CommandHandler("setadmin_crypto", setadmin_crypto, filters=private_filter))
    application.add_handler(CommandHandler("setadmin_upi", setadmin_upi, filters=private_filter))
    
    # Group command (verification group only)
    application.add_handler(CommandHandler("verify", verify, filters=group_filter))
    
    logger.info("Bot is starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot has stopped.")

if __name__ == '__main__':
    main()