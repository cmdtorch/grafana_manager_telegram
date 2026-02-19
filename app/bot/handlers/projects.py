from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings
from app.services.grafana import GrafanaError, GrafanaService

router = Router()


def _is_admin(message: Message) -> bool:
    return message.chat.id == settings.TELEGRAM_ADMIN_CHAT_ID


# ------------------------------------------------------------------
# /start  /help
# ------------------------------------------------------------------


@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Unauthorized.")
        return

    await message.answer(
        "<b>Grafana Manager — available commands:</b>\n\n"
        "/create_project &lt;name&gt; &lt;chat_id&gt;\n"
        "  Create a Grafana organization with Prometheus, Loki,\n"
        "  Tempo datasources, a dashboard folder, and a Telegram\n"
        "  alert contact point.\n\n"
        "/list_projects\n"
        "  List all Grafana organizations (excluding Main Org).\n\n"
        "/delete_project &lt;name&gt;\n"
        "  Delete a Grafana organization and all its data.\n\n"
        "/help — show this message"
    )


# ------------------------------------------------------------------
# /create_project <name> <chat_id>
# ------------------------------------------------------------------


@router.message(Command("create_project"))
async def cmd_create_project(message: Message, grafana: GrafanaService) -> None:
    if not _is_admin(message):
        await message.answer("Unauthorized.")
        return

    args = (message.text or "").split(maxsplit=2)[1:]
    if len(args) < 2:
        await message.answer(
            "Usage: /create_project &lt;project_name&gt; &lt;telegram_chat_id&gt;"
        )
        return

    project_name, chat_id = args[0], args[1]
    safe_name = escape(project_name)

    await message.answer(f"Creating project <b>{safe_name}</b>…")

    try:
        org_id = await grafana.create_organization(project_name)
        await grafana.add_datasources(org_id, project_name)
        await grafana.create_folder(org_id, project_name)
        await grafana.create_telegram_contact_point(
            org_id, settings.TELEGRAM_BOT_TOKEN, chat_id
        )
        await grafana.set_notification_policy(org_id)

        await message.answer(
            f"Project <b>{safe_name}</b> created successfully.\n"
            f"Org ID: <code>{org_id}</code>\n"
            f"Datasources: Prometheus, Loki, Tempo\n"
            f"Alerts → chat <code>{escape(chat_id)}</code>"
        )
    except GrafanaError as exc:
        await message.answer(f"Error: {escape(str(exc))}")
    except Exception as exc:
        await message.answer(f"Unexpected error: {escape(str(exc))}")


# ------------------------------------------------------------------
# /list_projects
# ------------------------------------------------------------------


@router.message(Command("list_projects"))
async def cmd_list_projects(message: Message, grafana: GrafanaService) -> None:
    if not _is_admin(message):
        await message.answer("Unauthorized.")
        return

    try:
        orgs = await grafana.list_organizations()
        if not orgs:
            await message.answer("No projects found.")
            return

        lines = [f"• <b>{escape(o['name'])}</b> (ID: {o['id']})" for o in orgs]
        await message.answer("<b>Projects:</b>\n" + "\n".join(lines))
    except GrafanaError as exc:
        await message.answer(f"Error: {escape(str(exc))}")
    except Exception as exc:
        await message.answer(f"Unexpected error: {escape(str(exc))}")


# ------------------------------------------------------------------
# /delete_project <name>
# ------------------------------------------------------------------


@router.message(Command("delete_project"))
async def cmd_delete_project(message: Message, grafana: GrafanaService) -> None:
    if not _is_admin(message):
        await message.answer("Unauthorized.")
        return

    args = (message.text or "").split(maxsplit=1)[1:]
    if not args:
        await message.answer("Usage: /delete_project &lt;project_name&gt;")
        return

    project_name = args[0].strip()
    safe_name = escape(project_name)

    try:
        org = await grafana.get_organization_by_name(project_name)
        if org is None:
            await message.answer(f"Project <b>{safe_name}</b> not found.")
            return

        await grafana.delete_organization(org["id"])
        await message.answer(f"Project <b>{safe_name}</b> deleted successfully.")
    except GrafanaError as exc:
        await message.answer(f"Error: {escape(str(exc))}")
    except Exception as exc:
        await message.answer(f"Unexpected error: {escape(str(exc))}")


# ------------------------------------------------------------------
# Catch-all for unauthorized users
# ------------------------------------------------------------------


@router.message()
async def catch_all(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Unauthorized.")
