from aiogram import Router

from app.bot.handlers import projects

main_router = Router()
main_router.include_router(projects.router)
