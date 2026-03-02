import os
import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    MessageHandler, 
    CommandHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    ConversationHandler, 
    filters
)
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import crud, models
from app.db.db import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SELECTING_CHAT, SELECTING_DATE = range(2)

class UnifiedTelegramBot:
    def __init__(self, token: str, admin_ids: list):
        self.token = token
        self.admin_ids = admin_ids
        self.application = None
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id in self.admin_ids:
            await update.message.reply_text(
                "👋 Добро пожаловать, администратор!\n\n"
                "Я буду собирать сообщения из этого чата, а также отвечать на команды:\n"
                "/chats - список чатов\n"
                "/export - экспорт сообщений\n"
                "/stats - статистика\n"
                "/help - помощь"
            )
        else:
            await update.message.reply_text(
                "👋 Привет! Я бот для сбора сообщений.\n"
                "Я буду сохранять все сообщения для последующего анализа."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message and not update.channel_post:
            return
        
        message = update.message or update.channel_post
        db = SessionLocal()
        
        try:
            if message.text and message.text.startswith('/'):
                return
            
            chat = crud.get_chat_by_telegram_id(db, message.chat_id)
            if not chat:
                chat = crud.create_chat(db, {
                    "chat_id": message.chat_id,
                    "title": message.chat.title or message.chat.effective_name or f"Chat_{message.chat_id}",
                    "chat_type": message.chat.type
                })
            
            user = None
            if message.from_user:
                user = crud.get_user_by_telegram_id(db, message.from_user.id)
                if not user:
                    is_admin = message.from_user.id in self.admin_ids
                    
                    user = crud.create_user(db, {
                        "user_id": message.from_user.id,
                        "username": message.from_user.username,
                        "first_name": message.from_user.first_name,
                        "last_name": message.from_user.last_name,
                        "is_bot": message.from_user.is_bot,
                        "is_admin": is_admin
                    })
            
            file_path = None
            file_type = None
            
            if message.photo:
                file_type = "photo"
                file = await self.download_file(message.photo[-1].file_id, "photo")
                file_path = file
            elif message.document:
                file_type = "document"
                file = await self.download_file(message.document.file_id, "doc")
                file_path = file
            elif message.video:
                file_type = "video"
                file = await self.download_file(message.video.file_id, "video")
                file_path = file
            elif message.audio:
                file_type = "audio"
                file = await self.download_file(message.audio.file_id, "audio")
                file_path = file
            elif message.voice:
                file_type = "voice"
                file = await self.download_file(message.voice.file_id, "voice")
                file_path = file
            elif message.sticker:
                file_type = "sticker"
                file = await self.download_file(message.sticker.file_id, "sticker")
                file_path = file
            
            message_data = {
                "message_id": message.message_id,
                "chat_id": chat.id,
                "user_id": user.id if user else None,
                "text": message.text or message.caption,
                "file_path": file_path,
                "file_type": file_type,
                "reply_to_message_id": message.reply_to_message.message_id if message.reply_to_message else None
            }
            
            crud.create_message(db, message_data)
            logger.info(f"Saved message {message.message_id} from chat {message.chat_id}")
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
        finally:
            db.close()
    
    async def download_file(self, file_id: str, file_type: str) -> str:
        try:
            file = await self.application.bot.get_file(file_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            file_ext = "bin"
            if file.file_path:
                file_ext = file.file_path.split('.')[-1] if '.' in file.file_path else 'bin'
            
            filename = f"{file_type}_{timestamp}_{file_id[:10]}.{file_ext}"
            filepath = os.path.join(self.download_path, filename)
            
            await file.download_to_drive(filepath)
            logger.info(f"Downloaded file: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    def check_admin(self, update: Update) -> bool:
        user_id = update.effective_user.id
        if user_id not in self.admin_ids:
            update.message.reply_text("У вас нет прав.")
            return False
        return True
    
    async def list_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.check_admin(update):
            return
        
        db = SessionLocal()
        try:
            chats = crud.get_all_chats(db)
            if not chats:
                await update.message.reply_text("Нет сохраненных чатов.")
                return
            
            message = "📋 **Список чатов:**\n\n"
            for chat in chats:
                msg_count = db.query(models.Message).filter(models.Message.chat_id == chat.id).count()
                file_count = db.query(models.Message).filter(
                    models.Message.chat_id == chat.id,
                    models.Message.file_path.isnot(None)
                ).count()
                
                message += f"• **{chat.title}** (ID: `{chat.chat_id}`)\n"
                message += f"Тип: {chat.chat_type} | Сообщений: {msg_count} | Файлов: {file_count}\n\n"
            
            if len(message) > 4000:
                for i in range(0, len(message), 4000):
                    await update.message.reply_text(message[i:i+4000], parse_mode='Markdown')
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
        finally:
            db.close()
    
    async def export_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.check_admin(update):
            return ConversationHandler.END
        
        db = SessionLocal()
        try:
            chats = crud.get_all_chats(db)
            if not chats:
                await update.message.reply_text("Нет чатов для экспорта.")
                return ConversationHandler.END
            
            keyboard = []
            for chat in chats:
                msg_count = db.query(models.Message).filter(models.Message.chat_id == chat.id).count()
                button_text = f"{chat.title} ({msg_count} сообщ.)"
                keyboard.append([InlineKeyboardButton(
                    button_text, 
                    callback_data=f"chat_{chat.id}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "**Выберите чат для экспорта:**",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return SELECTING_CHAT
        finally:
            db.close()
    
    async def chat_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        chat_id = int(query.data.split("_")[1])
        context.user_data['export_chat_id'] = chat_id
        
        keyboard = [
            [InlineKeyboardButton("За сегодня", callback_data="period_today")],
            [InlineKeyboardButton("За вчера", callback_data="period_yesterday")],
            [InlineKeyboardButton("За неделю", callback_data="period_week")],
            [InlineKeyboardButton("За месяц", callback_data="period_month")],
            [InlineKeyboardButton("Указать период", callback_data="period_custom")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "**Выберите период для экспорта:**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return SELECTING_DATE
    
    async def period_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        period = query.data.split("_")[1]
        end_date = datetime.now()
        
        if period == "today":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            period_text = "сегодня"
        elif period == "yesterday":
            start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
            period_text = "вчера"
        elif period == "week":
            start_date = end_date - timedelta(days=7)
            period_text = "последние 7 дней"
        elif period == "month":
            start_date = end_date - timedelta(days=30)
            period_text = "последние 30 дней"
        else:
            await query.edit_message_text("Введите даты в формате: ГГГГ-ММ-ДД ГГГГ-ММ-ДД")
            return SELECTING_DATE
        
        await query.edit_message_text(f"⏳ Экспортирую данные за {period_text}...")
        await self.perform_export(query, context, start_date, end_date)
        return ConversationHandler.END
    
    async def custom_date_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            dates = update.message.text.split()
            if len(dates) != 2:
                await update.message.reply_text(
                    "❌ Введите две даты в формате: ГГГГ-ММ-ДД ГГГГ-ММ-ДД\n"
                    "Например: 2026-02-01 2026-02-25"
                )
                return SELECTING_DATE
            
            start_date = datetime.strptime(dates[0], "%Y-%m-%d")
            end_date = datetime.strptime(dates[1], "%Y-%m-%d") + timedelta(days=1) - timedelta(microseconds=1)
            
            await update.message.reply_text(f"⏳ Экспортирую данные с {dates[0]} по {dates[1]}...")
            await self.perform_export(update, context, start_date, end_date)
        except ValueError:
            await update.message.reply_text(
                "❌ Введите две даты в формате: ГГГГ-ММ-ДД ГГГГ-ММ-ДД\n"
                "Например: 2026-02-01 2026-02-25"
            )
            return SELECTING_DATE
        
        return ConversationHandler.END
    
    async def perform_export(self, update_or_query, context, start_date, end_date):
        chat_id = context.user_data.get('export_chat_id')
        
        db = SessionLocal()
        try:
            import pandas as pd
            from io import BytesIO
            import os
            
            messages = crud.get_messages_by_chat_and_date(db, chat_id, start_date, end_date)
            chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
            
            if not messages:
                msg = "❌ Нет сообщений за выбранный период."
                if hasattr(update_or_query, 'edit_message_text'):
                    await update_or_query.edit_message_text(msg)
                else:
                    await update_or_query.reply_text(msg)
                return
            
            data = []
            for msg in messages:
                user = db.query(models.User).filter(models.User.id == msg.user_id).first()
                user_name = "Неизвестно"
                user_username = ""
                if user:
                    user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                    if user.username:
                        user_username = user.username
                        user_name += f" (@{user.username})"
                
                file_link = ""
                file_name = ""
                if msg.file_path and os.path.exists(msg.file_path):
                    file_name = os.path.basename(msg.file_path)
                    file_link = f"http://localhost:8000/files/{file_name}"
                
                data.append({
                    'ID сообщения': msg.message_id,
                    'Дата и время': msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'Пользователь': user_name,
                    'Username': user_username,
                    'ID пользователя': user.user_id if user else '',
                    'Текст сообщения': msg.text or '',
                    'Тип файла': msg.file_type or '',
                    'Имя файла': file_name,
                    'Ссылка на файл': file_link,
                    'Ответ на сообщение ID': msg.reply_to_message_id or ''
                })
            
            df = pd.DataFrame(data)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Сообщения', index=False)
                
                files_df = df[df['Тип файла'] != ''][['Тип файла', 'Имя файла', 'Ссылка на файл']]
                if not files_df.empty:
                    files_df.to_excel(writer, sheet_name='Файлы', index=False)
            
            output.seek(0)
            
            chat_title = chat.title.replace(' ', '_').replace('/', '-')[:50]
            filename = f"export_{chat_title}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
            
            files_count = len(df[df['Тип файла'] != ''])
            users_count = df['ID пользователя'].nunique()
            
            caption = (f"📊 **Экспорт чата {chat.title}**\n"
                      f"📅 Период: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}\n"
                      f"📝 Всего сообщений: {len(messages)}\n"
                      f"👥 Участников: {users_count}\n"
                      f"🖼 Файлов: {files_count}")
            
            if hasattr(update_or_query, 'edit_message_text'):
                await update_or_query.edit_message_text("✅ Экспорт готов, отправляю файл...")
                await update_or_query.message.reply_document(
                    document=output,
                    filename=filename,
                    caption=caption,
                    parse_mode='Markdown'
                )
            else:
                await update_or_query.reply_document(
                    document=output,
                    filename=filename,
                    caption=caption,
                    parse_mode='Markdown'
                )
            
            logger.info(f"Export completed for chat {chat.title}: {len(messages)} messages")
            
        except Exception as e:
            logger.error(f"Export error: {e}", exc_info=True)
            error_msg = f"❌ Ошибка при экспорте данных: {str(e)}"
            if hasattr(update_or_query, 'edit_message_text'):
                await update_or_query.edit_message_text(error_msg)
            else:
                await update_or_query.reply_text(error_msg)
        finally:
            db.close()
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.check_admin(update):
            return
        
        db = SessionLocal()
        try:
            total_chats = db.query(models.Chat).count()
            total_users = db.query(models.User).count()
            total_messages = db.query(models.Message).count()
            total_files = db.query(models.Message).filter(models.Message.file_path.isnot(None)).count()
            
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_messages = db.query(models.Message).filter(
                models.Message.created_at >= today_start
            ).count()
            
            stats_text = (
                f"**Статистика системы**\n\n"
                f"**Общая статистика:**\n"
                f"• Всего чатов: {total_chats}\n"
                f"• Всего пользователей: {total_users}\n"
                f"• Всего сообщений: {total_messages}\n"
                f"• Всего файлов: {total_files}\n"
                f"• Сообщений сегодня: {today_messages}\n"
            )
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Stats error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка при получении статистики: {str(e)}")
        finally:
            db.close()
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        help_text = (
            "**Справка по боту**\n\n"
            "Этот бот автоматически собирает все сообщения из чатов, "
            "в которые он добавлен, для последующего анализа.\n\n"
        )
        
        if user_id in self.admin_ids:
            help_text += (
                "**Команды администратора:**\n"
                "/chats - список всех чатов\n"
                "/export - экспорт сообщений за период\n"
                "/stats - статистика сбора\n"
                "/help - эта справка\n\n"
                "**Как экспортировать данные:**\n"
                "1. Отправьте команду /export\n"
                "2. Выберите чат из списка\n"
                "3. Выберите период\n"
                "4. Получите Excel файл"
            )
        else:
            help_text += (
                "Вы можете просто общаться в чате, а бот будет "
                "сохранять сообщения."
            )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Операция отменена.")
        return ConversationHandler.END
    
    async def run(self):
        self.application = Application.builder().token(self.token).build()
        
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("chats", self.list_chats))
        self.application.add_handler(CommandHandler("stats", self.stats))
        
        export_handler = ConversationHandler(
            entry_points=[CommandHandler("export", self.export_start)],
            states={
                SELECTING_CHAT: [CallbackQueryHandler(self.chat_selected, pattern="^chat_")],
                SELECTING_DATE: [
                    CallbackQueryHandler(self.period_selected, pattern="^period_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.custom_date_input)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        self.application.add_handler(export_handler)
        
        self.application.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND, 
            self.handle_message
        ))
        
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("Bot started successfully")
        logger.info(f"Admin IDs: {self.admin_ids}")
        
        while True:
            await asyncio.sleep(1)
    
    async def stop(self):
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Bot stopped successfully")