from aiogram import Router

from app.bot.handlers import groups, projects

main_router = Router()
main_router.include_router(groups.router)
main_router.include_router(projects.router)
