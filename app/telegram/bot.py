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
from app.db.db import SessionLocal, get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SELECTING_CHAT, SELECTING_DATE, ADDING_ADMIN = range(3)

class UnifiedTelegramBot:
    def __init__(self, token: str, initial_admin_ids: list):
        self.token = token
        self.initial_admin_ids = initial_admin_ids
        self.application = None
        self.settings = get_settings()
        self.download_path = self.settings["DOWNLOAD_PATH"]
        os.makedirs(self.download_path, exist_ok=True)
    
    async def check_admin(self, update: Update) -> bool:
        user_id = update.effective_user.id
        
        db = SessionLocal()
        try:
            user = crud.get_user_by_telegram_id(db, user_id)
            is_admin = user and user.is_admin
            
            if not is_admin:
                await update.message.reply_text("У вас нет прав администратора.")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking admin: {e}")
            return False
        finally:
            db.close()
    
    async def promote_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_admin(update):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("Использование: /promote_admin <user_id>")
            return
        
        try:
            new_admin_id = int(args[0])
            db = SessionLocal()
            try:
                user = crud.get_user_by_telegram_id(db, new_admin_id)
                if not user:
                    await update.message.reply_text("Пользователь не найден в базе данных.")
                    return
                
                crud.update_user(db, user.id, {"is_admin": True})
                await update.message.reply_text(f"✅ Пользователь {user.first_name or user.username} назначен администратором.")
                logger.info(f"User {new_admin_id} promoted to admin by {update.effective_user.id}")
            finally:
                db.close()
        except ValueError:
            await update.message.reply_text("ID пользователя должен быть числом.")
    
    async def demote_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_admin(update):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("Использование: /demote_admin <user_id>")
            return
        
        try:
            admin_id = int(args[0])
            
            if admin_id == update.effective_user.id:
                await update.message.reply_text("❌ Вы не можете удалить самого себя из администраторов.")
                return
            
            db = SessionLocal()
            try:
                user = crud.get_user_by_telegram_id(db, admin_id)
                if not user:
                    await update.message.reply_text("Пользователь не найден в базе данных.")
                    return
                
                crud.update_user(db, user.id, {"is_admin": False})
                await update.message.reply_text(f"Пользователь {user.first_name or user.username} удален из администраторов.")
                logger.info(f"User {admin_id} demoted by {update.effective_user.id}")
            finally:
                db.close()
        except ValueError:
            await update.message.reply_text("❌ ID пользователя должен быть числом.")
    
    async def list_admins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_admin(update):
            return
        
        db = SessionLocal()
        try:
            admins = crud.get_all_admins(db)
            if not admins:
                await update.message.reply_text("В системе нет администраторов.")
                return
            
            text = "Список администраторов:\n\n"
            for admin in admins:
                name = f"{admin.first_name or ''} {admin.last_name or ''}".strip()
                if not name:
                    name = admin.username or "Без имени"
                text += f"{name} (ID: {admin.user_id})\n"
            
            await update.message.reply_text(text)
        finally:
            db.close()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        db = SessionLocal()
        try:
            user = crud.get_user_by_telegram_id(db, user_id)
            if not user:
                is_admin = user_id in self.initial_admin_ids
                crud.create_user(db, {
                    "user_id": user_id,
                    "username": update.effective_user.username,
                    "first_name": update.effective_user.first_name,
                    "last_name": update.effective_user.last_name,
                    "is_bot": update.effective_user.is_bot,
                    "is_admin": is_admin
                })
                logger.info(f"New user registered: {user_id}, admin: {is_admin}")
        finally:
            db.close()
        
        is_admin = await self.check_admin(update)
        
        if is_admin:
            await update.message.reply_text(
                "👋 Добро пожаловать, администратор!\n\n"
                "Команды:\n"
                "/chats - список чатов\n"
                "/export - экспорт сообщений\n"
                "/stats - статистика\n"
                "/admins - список админов\n"
                "/promote_admin <id> - добавить админа\n"
                "/demote_admin <id> - удалить админа\n"
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
                    is_admin = message.from_user.id in self.initial_admin_ids
                    
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
    
    async def list_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_admin(update):
            return
        
        db = SessionLocal()
        try:
            chats = crud.get_all_chats(db)
            if not chats:
                await update.message.reply_text("Нет сохраненных чатов.")
                return
            
            message = "📋 Список чатов:\n\n"
            for chat in chats:
                msg_count = db.query(models.Message).filter(models.Message.chat_id == chat.id).count()
                file_count = db.query(models.Message).filter(
                    models.Message.chat_id == chat.id,
                    models.Message.file_path.isnot(None)
                ).count()
                
                message += f"{chat.title} (ID: {chat.chat_id})\n"
                message += f"Тип: {chat.chat_type} | Сообщений: {msg_count} | Файлов: {file_count}\n\n"
            
            if len(message) > 4000:
                for i in range(0, len(message), 4000):
                    await update.message.reply_text(message[i:i+4000])
            else:
                await update.message.reply_text(message)
        finally:
            db.close()
    
    async def export_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_admin(update):
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
                "Выберите чат для экспорта:",
                reply_markup=reply_markup
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
            "Выберите период для экспорта:",
            reply_markup=reply_markup
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
            
            await update.message.reply_text(f"Экспортирую данные с {dates[0]} по {dates[1]}...")
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
                msg = "Нет сообщений за выбранный период."
                if hasattr(update_or_query, 'edit_message_text'):
                    await update_or_query.edit_message_text(msg)
                else:
                    await update_or_query.reply_text(msg)
                return
            
            data = []
            for msg in messages:
                user = db.query(models.User).filter(models.User.id == msg.user_id).first()
                user_name = "Неизвестно"
                if user:
                    user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                    if user.username:
                        user_name += f" (@{user.username})"
                
                file_link = ""
                file_name = ""
                if msg.file_path and os.path.exists(msg.file_path):
                    file_name = os.path.basename(msg.file_path)
                    file_link = f"{self.settings['BASE_URL']}/files/{file_name}"
                
                data.append({
                    'ID сообщения': msg.message_id,
                    'Дата и время': msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'Пользователь': user_name,
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
            
            caption = (f"📊 Экспорт чата {chat.title}\n"
                      f"📅 Период: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}\n"
                      f"📝 Всего сообщений: {len(messages)}\n"
                      f"👥 Участников: {users_count}\n"
                      f"🖼 Файлов: {files_count}")
            
            if hasattr(update_or_query, 'edit_message_text'):
                await update_or_query.edit_message_text("Экспорт готов, отправляю файл...")
                await update_or_query.message.reply_document(
                    document=output,
                    filename=filename,
                    caption=caption
                )
            else:
                await update_or_query.reply_document(
                    document=output,
                    filename=filename,
                    caption=caption
                )
            
            logger.info(f"Export completed for chat {chat.title}: {len(messages)} messages")
            
        except Exception as e:
            logger.error(f"Export error: {e}", exc_info=True)
            error_msg = f"Ошибка при экспорте данных: {str(e)}"
            if hasattr(update_or_query, 'edit_message_text'):
                await update_or_query.edit_message_text(error_msg)
            else:
                await update_or_query.reply_text(error_msg)
        finally:
            db.close()
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_admin(update):
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
                f"Статистика системы\n\n"
                f"Общая статистика:\n"
                f"Всего чатов: {total_chats}\n"
                f"Всего пользователей: {total_users}\n"
                f"Всего сообщений: {total_messages}\n"
                f"Всего файлов: {total_files}\n"
                f"Сообщений сегодня: {today_messages}\n\n"
            )
            
            await update.message.reply_text(stats_text)
            
        except Exception as e:
            logger.error(f"Stats error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка при получении статистики: {str(e)}")
        finally:
            db.close()
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        db = SessionLocal()
        try:
            user = crud.get_user_by_telegram_id(db, user_id)
            is_admin = user and user.is_admin
        finally:
            db.close()
        
        help_text = (
            "Справка по боту\n\n"
            "Этот бот автоматически собирает все сообщения из чатов, "
            "в которые он добавлен.\n\n"
        )
        
        if is_admin:
            help_text += (
                "Команды администратора:\n"
                "/chats - список всех чатов\n"
                "/export - экспорт сообщений за период\n"
                "/stats - статистика сбора\n"
                "/admins - список администраторов\n"
                "/promote_admin <id> - добавить администратора\n"
                "/demote_admin <id> - удалить администратора\n"
                "/analyze <chat_id> [limit] - анализ сообщений через Yandex GPT\n"
                "/help - эта справка\n\n"
                "Как экспортировать данные:\n"
                "1. Отправьте команду /export\n"
                "2. Выберите чат из списка\n"
                "3. Выберите период\n"
                "4. Получите Excel файл"
            )
        else:
            help_text += (
                "Вы можете просто общаться в чате, а бот будет "
                "сохранять сообщения для администраторов."
            )
        
        await update.message.reply_text(help_text)

    async def analyze_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_admin(update):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "Использование: /analyze <chat_id> [limit]\n"
                "Пример: /analyze -100123456789 20"
            )
            return
        
        try:
            chat_telegram_id = int(args[0])
            limit = int(args[1]) if len(args) > 1 else 20
            
            db = SessionLocal()
            try:
                from app.llm.quality_analyzer import YandexMessageAnalyzer
                from app.db import models
                
                chat = crud.get_chat_by_telegram_id(db, chat_telegram_id)
                if not chat:
                    await update.message.reply_text(f"Чат с ID {chat_telegram_id} не найден в базе данных.")
                    return
                
                await update.message.reply_text(f"Анализирую последние {limit} сообщений...")
                
                messages = db.query(models.Message).filter(
                    models.Message.chat_id == chat.id
                ).order_by(models.Message.created_at.desc()).limit(limit).all()
                
                if not messages:
                    await update.message.reply_text("В чате нет сообщений для анализа.")
                    return
                
                messages_data = []
                for msg in messages:
                    if msg.text and len(msg.text.strip()) > 10:
                        messages_data.append({
                            'message_id': msg.id,
                            'text': msg.text
                        })
                
                if not messages_data:
                    await update.message.reply_text("Нет сообщений достаточной длины для анализа.")
                    return
                
                analyzer = YandexMessageAnalyzer()
                results = await analyzer.analyze_batch(messages_data)
                
                for result in results:
                    analysis_data = {
                        'message_id': result['message_id'],
                        **result['analysis']
                    }
                    crud.create_message_analysis(db, analysis_data)
                
                avg_score = sum(r['analysis']['quality_score'] for r in results) / len(results)
                needs_review = sum(1 for r in results if r['analysis']['needs_review'])
                questions = sum(1 for r in results if r['analysis']['is_question'])
                answers = sum(1 for r in results if r['analysis']['is_answer'])
                
                all_tags = []
                for r in results:
                    all_tags.extend(r['analysis']['tags'])
                
                tag_counts = {}
                for tag in all_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                
                top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                
                report = (
                    f"Результаты анализа чата {chat.title}\n\n"
                    f"Проанализировано сообщений: {len(results)}\n"
                    f"Средняя оценка качества: {avg_score:.1f}/10\n"
                    f"Требуют проверки: {needs_review}\n"
                    f"Вопросов: {questions}\n"
                    f"Ответов: {answers}\n\n"
                )
                
                await update.message.reply_text(report)
                
                keyboard = [
                    [InlineKeyboardButton("Да, отправить детальный отчет", callback_data=f"detail_{chat.id}_{limit}")],
                    [InlineKeyboardButton("Нет, спасибо", callback_data="cancel_detail")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "Хотите получить детальный отчет по каждому сообщению в Excel?",
                    reply_markup=reply_markup
                )
                
            finally:
                db.close()
                
        except ValueError:
            await update.message.reply_text("ID чата и лимит должны быть числами.")
        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            await update.message.reply_text(f"Ошибка при анализе: {str(e)}")

    async def send_detailed_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel_detail":
            await query.edit_message_text("Отменено.")
            return
        
        parts = query.data.split('_')
        chat_id = int(parts[1])
        limit = int(parts[2])
        
        db = SessionLocal()
        try:
            import pandas as pd
            from io import BytesIO
            
            await query.edit_message_text("Формирую детальный отчет...")
            
            chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
            
            analyses = db.query(models.MessageAnalysis).join(
                models.Message
            ).filter(
                models.Message.chat_id == chat_id
            ).order_by(
                models.MessageAnalysis.analyzed_at.desc()
            ).limit(limit).all()
            
            if not analyses:
                await query.edit_message_text("Нет данных для детального отчета.")
                return
            
            data = []
            for analysis in analyses:
                message = db.query(models.Message).filter(models.Message.id == analysis.message_id).first()
                user = db.query(models.User).filter(models.User.id == message.user_id).first() if message else None
                
                user_name = "Неизвестно"
                if user:
                    user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                    if user.username:
                        user_name += f" (@{user.username})"
                
                data.append({
                    'ID сообщения': message.message_id if message else analysis.message_id,
                    'Дата': message.created_at.strftime("%Y-%m-%d %H:%M:%S") if message else '',
                    'Пользователь': user_name,
                    'Оценка качества': analysis.quality_score,
                    'Тональность': analysis.sentiment,
                    'Вопрос': 'Да' if analysis.is_question else 'Нет',
                    'Ответ': 'Да' if analysis.is_answer else 'Нет',
                    'Требует проверки': 'Да' if analysis.needs_review else 'Нет',
                    'Теги': analysis.tags,
                    'Краткое содержание': analysis.summary,
                    'Текст сообщения': message.text[:200] + '...' if message and message.text and len(message.text) > 200 else (message.text if message else '')
                })
            
            df = pd.DataFrame(data)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Анализ сообщений', index=False)
            
            output.seek(0)
            
            filename = f"analysis_{chat.title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            await query.message.reply_document(
                document=output,
                filename=filename,
                caption=f"Детальный анализ чата {chat.title}"
            )
            
            await query.delete_message()
            
        except Exception as e:
            logger.error(f"Detail analysis error: {e}")
            await query.edit_message_text(f"Ошибка при формировании отчета: {str(e)}")
        finally:
            db.close()
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Операция отменена.")
        return ConversationHandler.END
    
    async def run(self):
        self.application = Application.builder().token(self.token).build()
        
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("chats", self.list_chats))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("analyze", self.analyze_chat))
        self.application.add_handler(CallbackQueryHandler(self.send_detailed_analysis, pattern="^(detail_|cancel_detail)"))
        self.application.add_handler(CommandHandler("admins", self.list_admins))
        self.application.add_handler(CommandHandler("promote_admin", self.promote_admin))
        self.application.add_handler(CommandHandler("demote_admin", self.demote_admin))
        
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
        
        db = SessionLocal()
        try:
            for admin_id in self.initial_admin_ids:
                user = crud.get_user_by_telegram_id(db, admin_id)
                if user and not user.is_admin:
                    crud.update_user(db, user.id, {"is_admin": True})
                    logger.info(f"Initial admin {admin_id} activated in DB")
        finally:
            db.close()
        
        while True:
            await asyncio.sleep(1)
    
    async def stop(self):
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Bot stopped successfully")