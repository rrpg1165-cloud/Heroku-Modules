# +----------------------+
# |  ╦ ╦╔═╗╦═╗╔═╗╦╔═╦ ╦  |
# |  ╠═╣║╣ ╠╦╝║ ║╠╩╗║ ║  |
# |  ╩ ╩╚═╝╩╚═╚═╝╩ ╩╚═╝  |
# +----------------------+
# meta developer: @heroku_mods
# meta banner: https://raw.githubusercontent.com/rrpg1165-cloud/Heroku-Modules/main/Heroku/Modules/Giveaways/Heroku/banner.jpg
# scope: heroku_min 2.2.0

import asyncio
import html as html_lib
import logging
import time

from herokutl.errors import FloodWaitError, RPCError, UserAlreadyParticipantError, UserNotParticipantError
from herokutl.tl.functions.channels import GetParticipantRequest, JoinChannelRequest, LeaveChannelRequest
from herokutl.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest
from herokutl.tl.functions.payments import GetGiveawayInfoRequest
from herokutl.tl.types import (
    DialogFilter,
    InputPeerSelf,
    Message,
    MessageMediaGiveaway,
    PeerChannel,
    TextWithEntities,
)
from herokutl.tl.types.payments import GiveawayInfoResults

from .. import loader, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

FOLDER_NAME = "Розыгрыши"
TOPIC_TITLE = "Giveaways"
MAX_ATTEMPTS = 3
PROGRESS_EVERY = 2
FAIL_LIMIT = 5
RESULT_GIVE_UP = 3 * 86400

# Premium emoji from the owner's packs: name -> (document id, alt)
EMOJI = {
    "on": ("5445279663809130789", "🔛"),
    "off": ("5445349654596189741", "📴"),
    "search": ("5444989577422993015", "🔍"),
    "ok": ("5444987348334965906", "✅"),
    "bell": ("5445333299360723379", "🔔"),
    "stats": ("5445146408153806223", "📊"),
    "warn": ("5447381715293074599", "⚠️"),
    "star": ("5444939047132755535", "⭐️"),
    "gem": ("5260681660189408650", "💎"),
    "medal": ("5444931419270839381", "🏅"),
    "time": ("5445350406215465190", "⏰"),
    "info": ("5247236071795754971", "ℹ️"),
}


@loader.tds
class GiveawaysMod(loader.Module):
    """Joins Telegram giveaways automatically, keeps their history and leaves sponsor channels afterwards"""

    strings = {
        "name": "Giveaways",
        "gw_on": "Auto participation enabled",
        "gw_off": "Auto participation disabled",
        "gw_on_hint": "New giveaways are handled automatically",
        "gw_off_hint": "New giveaways are ignored",
        "scan_run": "Scanning chat history",
        "scan_now": "Now: <b>{}</b>",
        "scan_loading": "loading chat list",
        "scan_busy": "A scan is already running",
        "scan_done": "Scan finished",
        "scan_stopped": "Scan stopped",
        "scan_stopping": "Stopping after the current chat",
        "scan_chats": "Chats checked",
        "scan_found": "New giveaways",
        "scan_results": "Found: {}",
        "btn_stop": "Stop",
        "btn_close": "Close",
        "limiter_title": "Joining channels is blocked",
        "limiter_hint": "APILimiter forbids joinChannel, so giveaways cannot be joined. Remove joinChannel from forbidden_methods in .config APILimiter",
        "st_title": "Active giveaways",
        "st_count": "Total: <b>{}</b>",
        "st_empty": "No active giveaways",
        "stats_title": "Statistics",
        "stat_joined": "Participated",
        "stat_wins": "Wins",
        "stat_total": "Channels subscribed in total",
        "stat_now": "Subscribed now",
        "stat_left": "Left",
        "stat_active": "Active giveaways",
        "stat_wait": "Awaiting results",
            "prize_stars": "{} stars",
        "prize_premium": "Premium for {} mo.",
        "prize_unknown": "Unknown prize",
                            "new_title": "Joined a giveaway",
        "fail_title": "Participation not confirmed",
        "win_title": "You won a giveaway",
        "l_prize": "Prize: {}",
        "l_until": "Ends: {}",
        "l_sponsors": "Sponsor channels: {}, new subscriptions: {}",
        "l_reason": "Reason: {}",
        "l_open": "Open the post",
        "r_early": "The giveaway is for new subscribers only, but this account was subscribed earlier ({}).",
        "r_admin": "A sponsor channel does not allow this account to participate.",
        "r_country": "The giveaway is not available in the country {}.",
        "r_preparing": "Telegram is already preparing the results, it is too late to join.",
        "r_new_only": "Telegram did not confirm participation. The giveaway is probably for new subscribers only.",
        "r_generic": "Telegram did not confirm participation after subscribing to the sponsors.",
        "_cfg_target": "Which giveaways to join: Premium only, Stars only or both",
        "_cfg_bot": "Send notifications through the inline bot",
        "_cfg_notify": "Chat or user ID for notifications (0 means the Giveaways topic in the log chat)",
        "_cfg_mute": "Mute sponsor channels after subscribing",
        "_cfg_archive": "Move sponsor channels to the archive right after subscribing",
        "_cfg_folder": "Create the folder with sponsor channels automatically",
        "_cfg_delay": "Delay between subscriptions in seconds",
        "_cfg_scan": "How many latest messages of each chat .gwscan checks",
        "_cfg_leave": "Leave sponsor channels after the giveaway ends",
        "_cfg_leave_hours": "Hours to wait after the end before leaving",
        }

    strings_ru = {
        "gw_on": "Авто-участие включено",
        "gw_off": "Авто-участие выключено",
        "gw_on_hint": "Новые розыгрыши обрабатываются автоматически",
        "gw_off_hint": "Новые розыгрыши игнорируются",
        "scan_run": "Сканирую историю чатов",
        "scan_now": "Сейчас: <b>{}</b>",
        "scan_loading": "загрузка списка чатов",
        "scan_busy": "Сканирование уже идёт",
        "scan_done": "Сканирование завершено",
        "scan_stopped": "Сканирование остановлено",
        "scan_stopping": "Останавливаю после текущего чата",
        "scan_chats": "Проверено чатов",
        "scan_found": "Новых розыгрышей",
        "scan_results": "Найдено: {}",
        "btn_stop": "Остановить",
        "btn_close": "Закрыть",
        "limiter_title": "Подписка на каналы запрещена",
        "limiter_hint": "APILimiter запрещает joinChannel, поэтому участвовать в розыгрышах нельзя. Убери joinChannel из forbidden_methods в .config APILimiter",
        "st_title": "Активные розыгрыши",
        "st_count": "Всего: <b>{}</b>",
        "st_empty": "Нет активных розыгрышей",
        "stats_title": "Статистика",
        "stat_joined": "Участвовал",
        "stat_wins": "Побед",
        "stat_total": "Подписался на каналов всего",
        "stat_now": "Сейчас в подписках",
        "stat_left": "Вышел из каналов",
        "stat_active": "Активных розыгрышей",
        "stat_wait": "Ждут итогов",
        "prize_stars": "{} звёзд",
        "prize_premium": "Премиум на {} мес.",
        "prize_unknown": "Неизвестный приз",
        "new_title": "Участвую в розыгрыше",
        "fail_title": "Участие не подтверждено",
        "win_title": "Ты выиграл розыгрыш",
        "l_prize": "Приз: {}",
        "l_until": "Конец: {}",
        "l_sponsors": "Каналов-спонсоров: {}, новых подписок: {}",
        "l_reason": "Причина: {}",
        "l_open": "Открыть пост",
        "r_early": "Розыгрыш только для новых подписчиков, а аккаунт был подписан раньше ({}).",
        "r_admin": "Один из спонсорских каналов запретил участие этому аккаунту.",
        "r_country": "Розыгрыш недоступен для страны {}.",
        "r_preparing": "Telegram уже готовит результаты, вступать поздно.",
        "r_new_only": "Telegram не подтвердил участие. Похоже, розыгрыш только для новых подписчиков.",
        "r_generic": "Telegram не подтвердил участие после подписки на спонсоров.",
        "_cfg_target": "В каких розыгрышах участвовать: только Premium, только Stars или во всех",
        "_cfg_bot": "Отправлять уведомления через инлайн-бота",
        "_cfg_notify": "ID чата или юзера для уведомлений (0 - топик Giveaways в чате логов)",
        "_cfg_mute": "Отключать звук в спонсорских каналах после подписки",
        "_cfg_archive": "Сразу отправлять спонсорские каналы в архив после подписки",
        "_cfg_folder": "Автоматически создавать папку со спонсорскими каналами",
        "_cfg_delay": "Задержка между подписками в секундах",
        "_cfg_scan": "Сколько последних сообщений каждого чата проверяет .gwscan",
        "_cfg_leave": "Выходить из спонсорских каналов после конца розыгрыша",
        "_cfg_leave_hours": "Сколько часов ждать после конца перед выходом",
    }

    strings_uk = {
        "gw_on": "Авто-участь увімкнено",
        "gw_off": "Авто-участь вимкнено",
        "gw_on_hint": "Нові розіграші обробляються автоматично",
        "gw_off_hint": "Нові розіграші ігноруються",
        "scan_run": "Скануюю історію чатів",
        "scan_now": "Зараз: <b>{}</b>",
        "scan_loading": "завантаження списку чатів",
        "scan_busy": "Сканування вже триває",
        "scan_done": "Сканування завершено",
        "scan_stopped": "Сканування зупинено",
        "scan_stopping": "Зупиняю після поточного чату",
        "scan_chats": "Перевірено чатів",
        "scan_found": "Нових розіграшів",
        "scan_results": "Знайдено: {}",
        "btn_stop": "Зупинити",
        "btn_close": "Закрити",
        "limiter_title": "Підписку на канали заборонено",
        "limiter_hint": "APILimiter забороняє joinChannel, тому брати участь у розіграшах не можна. Прибери joinChannel із forbidden_methods у .config APILimiter",
        "st_title": "Активні розіграші",
        "st_count": "Усього: <b>{}</b>",
        "st_empty": "Немає активних розіграшів",
        "stats_title": "Статистика",
        "stat_joined": "Брав участь",
        "stat_wins": "Перемог",
        "stat_total": "Підписався на каналів усього",
        "stat_now": "Зараз у підписках",
        "stat_left": "Вийшов із каналів",
        "stat_active": "Активних розіграшів",
        "stat_wait": "Чекають на підсумки",
        "prize_stars": "{} зірок",
        "prize_premium": "Преміум на {} міс.",
        "prize_unknown": "Невідомий приз",
        "new_title": "Беру участь у розіграші",
        "fail_title": "Участь не підтверджено",
        "win_title": "Ти виграв розіграш",
        "l_prize": "Приз: {}",
        "l_until": "Кінець: {}",
        "l_sponsors": "Каналів-спонсорів: {}, нових підписок: {}",
        "l_reason": "Причина: {}",
        "l_open": "Відкрити допис",
        "r_early": "Розіграш лише для нових підписників, а акаунт був підписаний раніше ({}).",
        "r_admin": "Один зі спонсорських каналів заборонив участь цьому акаунту.",
        "r_country": "Розіграш недоступний для країни {}.",
        "r_preparing": "Telegram уже готує результати, вступати пізно.",
        "r_new_only": "Telegram не підтвердив участь. Схоже, розіграш лише для нових підписників.",
        "r_generic": "Telegram не підтвердив участь після підписки на спонсорів.",
        "_cfg_target": "У яких розіграшах брати участь: лише Premium, лише Stars або в усіх",
        "_cfg_bot": "Надсилати сповіщення через інлайн-бота",
        "_cfg_notify": "ID чату або користувача для сповіщень (0 - топік Giveaways у чаті логів)",
        "_cfg_mute": "Вимикати звук у спонсорських каналах після підписки",
        "_cfg_archive": "Одразу надсилати спонсорські канали в архів після підписки",
        "_cfg_folder": "Автоматично створювати папку зі спонсорськими каналами",
        "_cfg_delay": "Затримка між підписками в секундах",
        "_cfg_scan": "Скільки останніх повідомлень кожного чату перевіряє .gwscan",
        "_cfg_leave": "Виходити зі спонсорських каналів після кінця розіграшу",
        "_cfg_leave_hours": "Скільки годин чекати після кінця перед виходом",
    }

    strings_de = {
        "gw_on": "Automatische Teilnahme aktiviert",
        "gw_off": "Automatische Teilnahme deaktiviert",
        "gw_on_hint": "Neue Gewinnspiele werden automatisch bearbeitet",
        "gw_off_hint": "Neue Gewinnspiele werden ignoriert",
        "scan_run": "Chatverlauf wird gescannt",
        "scan_now": "Aktuell: <b>{}</b>",
        "scan_loading": "Chatliste wird geladen",
        "scan_busy": "Ein Scan läuft bereits",
        "scan_done": "Scan abgeschlossen",
        "scan_stopped": "Scan gestoppt",
        "scan_stopping": "Stoppe nach dem aktuellen Chat",
        "scan_chats": "Chats geprüft",
        "scan_found": "Neue Gewinnspiele",
        "scan_results": "Gefunden: {}",
        "btn_stop": "Stoppen",
        "btn_close": "Schließen",
        "limiter_title": "Das Abonnieren von Kanälen ist blockiert",
        "limiter_hint": "APILimiter verbietet joinChannel, daher ist die Teilnahme an Gewinnspielen nicht möglich. Entferne joinChannel aus forbidden_methods in .config APILimiter",
        "st_title": "Aktive Gewinnspiele",
        "st_count": "Insgesamt: <b>{}</b>",
        "st_empty": "Keine aktiven Gewinnspiele",
        "stats_title": "Statistik",
        "stat_joined": "Teilgenommen",
        "stat_wins": "Gewinne",
        "stat_total": "Kanäle insgesamt abonniert",
        "stat_now": "Aktuell abonniert",
        "stat_left": "Kanäle verlassen",
        "stat_active": "Aktive Gewinnspiele",
        "stat_wait": "Warten auf Ergebnisse",
        "prize_stars": "{} Sterne",
        "prize_premium": "Premium für {} Mon.",
        "prize_unknown": "Unbekannter Preis",
        "new_title": "Nehme an einem Gewinnspiel teil",
        "fail_title": "Teilnahme nicht bestätigt",
        "win_title": "Du hast ein Gewinnspiel gewonnen",
        "l_prize": "Preis: {}",
        "l_until": "Ende: {}",
        "l_sponsors": "Sponsorkanäle: {}, neue Abonnements: {}",
        "l_reason": "Grund: {}",
        "l_open": "Beitrag öffnen",
        "r_early": "Das Gewinnspiel gilt nur für neue Abonnenten, aber das Konto war früher abonniert ({}).",
        "r_admin": "Ein Sponsorkanal erlaubt diesem Konto die Teilnahme nicht.",
        "r_country": "Das Gewinnspiel ist im Land {} nicht verfügbar.",
        "r_preparing": "Telegram bereitet bereits die Ergebnisse vor, zum Beitreten ist es zu spät.",
        "r_new_only": "Telegram hat die Teilnahme nicht bestätigt. Vermutlich gilt das Gewinnspiel nur für neue Abonnenten.",
        "r_generic": "Telegram hat die Teilnahme nach dem Abonnieren der Sponsoren nicht bestätigt.",
        "_cfg_target": "An welchen Gewinnspielen teilnehmen: nur Premium, nur Stars oder an allen",
        "_cfg_bot": "Benachrichtigungen über den Inline-Bot senden",
        "_cfg_notify": "Chat- oder Nutzer-ID für Benachrichtigungen (0 - Thema Giveaways im Log-Chat)",
        "_cfg_mute": "Sponsorkanäle nach dem Abonnieren stummschalten",
        "_cfg_archive": "Sponsorkanäle nach dem Abonnieren sofort archivieren",
        "_cfg_folder": "Ordner mit Sponsorkanälen automatisch erstellen",
        "_cfg_delay": "Verzögerung zwischen Abonnements in Sekunden",
        "_cfg_scan": "Wie viele letzte Nachrichten jedes Chats .gwscan prüft",
        "_cfg_leave": "Sponsorkanäle nach dem Ende des Gewinnspiels verlassen",
        "_cfg_leave_hours": "Wie viele Stunden nach dem Ende vor dem Verlassen gewartet wird",
    }

    strings_ja = {
        "gw_on": "自動参加を有効にしました",
        "gw_off": "自動参加を無効にしました",
        "gw_on_hint": "新しいプレゼント企画は自動で処理されます",
        "gw_off_hint": "新しいプレゼント企画は無視されます",
        "scan_run": "チャット履歴をスキャン中",
        "scan_now": "現在: <b>{}</b>",
        "scan_loading": "チャット一覧を読み込み中",
        "scan_busy": "スキャンはすでに実行中です",
        "scan_done": "スキャンが完了しました",
        "scan_stopped": "スキャンを停止しました",
        "scan_stopping": "現在のチャットの後で停止します",
        "scan_chats": "確認したチャット",
        "scan_found": "新しいプレゼント企画",
        "scan_results": "見つかった数: {}",
        "btn_stop": "停止",
        "btn_close": "閉じる",
        "limiter_title": "チャンネル登録がブロックされています",
        "limiter_hint": "APILimiter が joinChannel を禁止しているため、プレゼント企画に参加できません。.config APILimiter の forbidden_methods から joinChannel を外してください",
        "st_title": "進行中のプレゼント企画",
        "st_count": "合計: <b>{}</b>",
        "st_empty": "進行中のプレゼント企画はありません",
        "stats_title": "統計",
        "stat_joined": "参加数",
        "stat_wins": "当選数",
        "stat_total": "登録したチャンネルの合計",
        "stat_now": "現在登録中",
        "stat_left": "退出したチャンネル",
        "stat_active": "進行中の企画",
        "stat_wait": "結果待ち",
        "prize_stars": "{} スター",
        "prize_premium": "プレミアム {} か月",
        "prize_unknown": "不明な賞品",
        "new_title": "プレゼント企画に参加しました",
        "fail_title": "参加を確認できませんでした",
        "win_title": "プレゼント企画に当選しました",
        "l_prize": "賞品: {}",
        "l_until": "終了: {}",
        "l_sponsors": "スポンサーチャンネル: {}、新規登録: {}",
        "l_reason": "理由: {}",
        "l_open": "投稿を開く",
        "r_early": "この企画は新規登録者限定ですが、このアカウントは以前から登録していました ({})。",
        "r_admin": "スポンサーチャンネルの1つがこのアカウントの参加を許可していません。",
        "r_country": "この企画は {} では利用できません。",
        "r_preparing": "Telegram はすでに結果を準備中のため、参加できません。",
        "r_new_only": "Telegram が参加を確認しませんでした。新規登録者限定の企画の可能性があります。",
        "r_generic": "スポンサーに登録した後も Telegram が参加を確認しませんでした。",
        "_cfg_target": "参加する企画: Premium のみ、Stars のみ、またはすべて",
        "_cfg_bot": "インラインボット経由で通知を送る",
        "_cfg_notify": "通知先のチャットまたはユーザー ID (0 はログチャットの Giveaways トピック)",
        "_cfg_mute": "登録後にスポンサーチャンネルをミュートする",
        "_cfg_archive": "登録後にスポンサーチャンネルをすぐアーカイブする",
        "_cfg_folder": "スポンサーチャンネルのフォルダを自動作成する",
        "_cfg_delay": "登録間の待ち時間 (秒)",
        "_cfg_scan": ".gwscan が各チャットで確認する最新メッセージ数",
        "_cfg_leave": "企画の終了後にスポンサーチャンネルから退出する",
        "_cfg_leave_hours": "終了後、退出までに待つ時間 (時間)",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "target_giveaways",
                "Premium+Stars",
                lambda: self.strings["_cfg_target"],
                validator=loader.validators.Choice(["Premium", "Stars", "Premium+Stars"]),
            ),
            loader.ConfigValue(
                "send_via_bot",
                True,
                lambda: self.strings["_cfg_bot"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "notify_user_id",
                0,
                lambda: self.strings["_cfg_notify"],
                validator=loader.validators.Integer(),
            ),
            loader.ConfigValue(
                "mute_channels",
                True,
                lambda: self.strings["_cfg_mute"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "archive_channels",
                True,
                lambda: self.strings["_cfg_archive"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "auto_create_folder",
                True,
                lambda: self.strings["_cfg_folder"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "join_delay",
                2.5,
                lambda: self.strings["_cfg_delay"],
                validator=loader.validators.Float(minimum=0.5),
            ),
            loader.ConfigValue(
                "scan_history_limit",
                200,
                lambda: self.strings["_cfg_scan"],
                validator=loader.validators.Integer(minimum=10, maximum=1000),
            ),
            loader.ConfigValue(
                "auto_leave",
                True,
                lambda: self.strings["_cfg_leave"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "leave_after_hours",
                24,
                lambda: self.strings["_cfg_leave_hours"],
                validator=loader.validators.Integer(minimum=0, maximum=720),
            ),
        )

    async def client_ready(self):
        self._lock = asyncio.Lock()
        self._scanning = False
        self._scan_halt = False
        self._topic = None
        self._scan_task = None
        self._scan_msg = None
        self._scan_state = None
        self._retry = {}
        self._giveaways = self.get("giveaways", {})
        self._channels = self.get("channels", {})
        self._skip = dict.fromkeys(self.get("skipped", []))
        self._folder_id = self.get("folder_id", None)

    # ---------- emoji, rendering, answers ----------

    def _premium(self) -> bool:
        return getattr(self._client.heroku_me, "premium", False) is True

    def _e(self, name: str) -> str:
        emoji_id, alt = EMOJI[name]
        if self._premium():
            return f'<tg-emoji emoji-id="{emoji_id}">{alt}</tg-emoji>'
        return alt

    def _when(self, ts: int, rich: bool) -> str:
        text = time.strftime("%d.%m %H:%M UTC", time.gmtime(ts))
        if rich:
            return f'<tg-time unix="{int(ts)}" format="dt">{text}</tg-time>'
        return text

    def _join_blocked(self) -> bool:
        limiter = self.lookup("APILimiter")
        if limiter is None:
            return False
        try:
            return "joinChannel" in limiter.config["forbidden_methods"]
        except Exception as e:
            logger.debug("APILimiter config is unreadable: %s", e)
            return False

    def _limiter_card(self, rich: bool) -> dict:
        return {
            "emoji": "warn",
            "title": self.strings["limiter_title"],
            "lines": [utils.escape_html(self.strings["limiter_hint"])],
        }

    def _a(self, link: str, text: str) -> str:
        text = utils.escape_html(text)
        if not link:
            return text
        return f'<a href="{html_lib.escape(link, quote=True)}">{text}</a>'

    def _render(self, card: dict, rich: bool) -> str:
        head = f"{self._e(card['emoji'])} {card['title']}"
        lines = card.get("lines", [])
        rows = card.get("rows", [])
        items = card.get("items", [])
        sections = card.get("sections", [])
        if rich:
            out = [f"<h4>{head}</h4>"]
            out += [f"<p>{line}</p>" for line in lines]
            if rows:
                cells = "".join(f"<tr><td>{k}</td><td><code>{v}</code></td></tr>" for k, v in rows)
                out.append(f"<table bordered compact>{cells}</table>")
            if items:
                out.append("<ol>" + "".join(f"<li>{item}</li>" for item in items) + "</ol>")
            for summary, entries in sections:
                body = "".join(f"<li>{item}</li>" for item in entries)
                out.append(f"<details><summary>{summary}</summary><ol>{body}</ol></details>")
            for label, data, style in card.get("buttons", []):
                out.append(
                    f'<tg-button-row><tg-button type="callback_data" data="{data}" style="{style}">'
                    f"{label}</tg-button></tg-button-row>"
                )
            return "".join(out)
        out = [f"<b>{head}</b>"] + lines
        out += [f"{k}: <code>{v}</code>" for k, v in rows]
        out += [f"{i}. {item}" for i, item in enumerate(items, 1)]
        for summary, entries in sections:
            numbered = "\n".join(f"{i}. {item}" for i, item in enumerate(entries, 1))
            out.append(f"<b>{summary}</b>\n<blockquote expandable>{numbered}</blockquote>")
        return "\n".join(out)

    async def _say(self, message, build):
        """Answer with a Rich message and fall back to plain HTML"""
        try:
            result = await utils.answer(message, "", rich_message=self._render(build(True), True))
        except RPCError as e:
            logger.warning("Rich message was rejected: %s", e)
            result = None
        if result:
            return result
        return await utils.answer(message, self._render(build(False), False))

    async def _log_topic(self):
        """Returns (log chat id, topic id) of the Giveaways topic or None"""
        if self._topic:
            return self._topic
        try:
            content_id = await utils.wait_for_content_channel(self.db)
            chat = int(f"-100{content_id}")
            topic = await utils.asset_forum_topic(self.client, self.db, chat, TOPIC_TITLE, invite_bot=True)
            self._topic = (chat, topic.id)
        except Exception as e:
            logger.warning("Giveaways topic is unavailable: %s", e)
            return None
        return self._topic

    async def _notify(self, build):
        chat, topic = self.config["notify_user_id"], None
        if not chat:
            target = await self._log_topic()
            chat, topic = target if target else (self.tg_id, None)
        plain = self._render(build(False), False)
        if self.config["send_via_bot"] and self.inline.init_complete:
            try:
                await self.inline.bot.send_rich_message(
                    chat, self._render(build(True), True), message_thread_id=topic
                )
                return
            except Exception as e:
                logger.warning("Bot notification failed: %s", e)
        try:
            await self.client.send_message(chat, plain, reply_to=topic, link_preview=False)
        except Exception as e:
            logger.warning("Notification failed: %s", e)

    # ---------- cards ----------

    def _prize(self, rec: dict):
        if rec.get("stars"):
            return "star", self.strings["prize_stars"].format(rec["stars"])
        if rec.get("months"):
            return "gem", self.strings["prize_premium"].format(rec["months"])
        return "info", self.strings["prize_unknown"]

    def _prize_line(self, rec: dict) -> str:
        emoji, prize = self._prize(rec)
        return self.strings["l_prize"].format(f"{self._e(emoji)} {utils.escape_html(prize)}")

    def _card_new(self, rec: dict, new_count: int, rich: bool) -> dict:
        s = self.strings
        return {
            "emoji": "ok",
            "title": s["new_title"],
            "lines": [
                self._prize_line(rec),
                s["l_until"].format(self._when(rec["until"], rich)),
                s["l_sponsors"].format(len(rec["channels"]), new_count),
                self._a(rec["link"], s["l_open"]),
            ],
        }

    def _card_fail(self, rec: dict, reason: str) -> dict:
        s = self.strings
        return {
            "emoji": "warn",
            "title": s["fail_title"],
            "lines": [
                self._prize_line(rec),
                s["l_reason"].format(utils.escape_html(reason)),
                self._a(rec["link"], s["l_open"]),
            ],
        }

    def _card_win(self, rec: dict) -> dict:
        s = self.strings
        return {
            "emoji": "medal",
            "title": s["win_title"],
            "lines": [self._prize_line(rec), self._a(rec["link"], s["l_open"])],
        }

    def _item(self, rec: dict, rich: bool) -> str:
        emoji, prize = self._prize(rec)
        return f"{self._e(emoji)} {self._a(rec['link'], prize)}, {self._when(rec['until'], rich)}"

    # ---------- storage ----------

    def _save_giveaways(self):
        self.set("giveaways", self._giveaways)

    def _save_channels(self):
        self.set("channels", self._channels)

    def _skip_add(self, uid: str):
        self._skip[uid] = None
        if len(self._skip) > 3000:
            for key in list(self._skip)[:1000]:
                del self._skip[key]
        self.set("skipped", list(self._skip))

    # ---------- telegram helpers ----------

    def _fingerprint(self, media) -> str:
        channels = sorted(int(c) for c in (getattr(media, "channels", None) or []))
        until = int(media.until_date.timestamp()) if getattr(media, "until_date", None) else 0
        countries = sorted(getattr(media, "countries_iso2", None) or [])
        return "|".join(
            [
                ",".join(map(str, channels)),
                str(until),
                str(int(getattr(media, "stars", 0) or 0)),
                str(int(getattr(media, "months", 0) or 0)),
                str(int(getattr(media, "quantity", 0) or 0)),
                str(int(bool(getattr(media, "only_new_subscribers", False)))),
                ",".join(countries),
            ]
        )

    async def _link(self, message) -> str:
        try:
            link = await utils.get_message_link(message)
            if link:
                return link
        except Exception as e:
            logger.debug("Message link failed: %s", e)
        return f"https://t.me/c/{str(message.chat_id).replace('-100', '', 1)}/{message.id}"

    async def _entity(self, channel_id: int):
        try:
            return await self.client.get_entity(PeerChannel(channel_id))
        except Exception as e:
            logger.debug("Channel %s was not resolved: %s", channel_id, e)
            return None

    async def _is_member(self, entity) -> bool:
        try:
            await self.client(GetParticipantRequest(entity, InputPeerSelf()))
            return True
        except UserNotParticipantError:
            return False
        except Exception as e:
            logger.debug("Membership check failed: %s", e)
            return False

    async def _join(self, entity) -> str:
        """Returns member (already was), joined or failed"""
        if await self._is_member(entity):
            return "member"
        for _ in range(2):
            try:
                await self.client(JoinChannelRequest(entity))
                break
            except UserAlreadyParticipantError:
                return "member"
            except FloodWaitError as e:
                if e.seconds > 300:
                    logger.warning("FloodWait %ss on join, giving up for now", e.seconds)
                    return "failed"
                await asyncio.sleep(e.seconds + 1)
            except Exception as e:
                logger.warning("Join failed: %s", e)
                return "failed"
        if not await self._is_member(entity):
            logger.warning("Join had no effect (check APILimiter settings): %s", getattr(entity, "id", entity))
            return "failed"
        return "joined"

    async def _tidy(self, entity):
        """Mute and/or archive a channel right after subscribing"""
        archive = self.config["archive_channels"]
        if self.config["mute_channels"]:
            await utils.dnd(self.client, entity, archive)
        elif archive:
            try:
                await self.client.edit_folder(entity, 1)
            except Exception as e:
                logger.warning("Archiving failed: %s", e)

    async def _leave(self, channel_id: int) -> bool:
        try:
            entity = await self.client.get_input_entity(PeerChannel(channel_id))
            await self.client(LeaveChannelRequest(entity))
            return True
        except UserNotParticipantError:
            return True
        except Exception as e:
            logger.warning("Leaving channel %s failed: %s", channel_id, e)
            return False

    async def _add_to_folder(self, entities):
        if not self.config["auto_create_folder"] or not entities:
            return
        try:
            result = await self.client(GetDialogFiltersRequest())
            filters = list(getattr(result, "filters", result))
            target = next(
                (
                    f
                    for f in filters
                    if isinstance(f, DialogFilter)
                    and (f.id == self._folder_id or getattr(f.title, "text", f.title) == FOLDER_NAME)
                ),
                None,
            )
            if target is None:
                new_id = max([getattr(f, "id", 1) for f in filters] + [1]) + 1
                target = DialogFilter(
                    id=new_id,
                    title=TextWithEntities(FOLDER_NAME, []),
                    pinned_peers=[],
                    include_peers=[],
                    exclude_peers=[],
                )

            def key(peer):
                return getattr(peer, "channel_id", None) or getattr(peer, "chat_id", None) or getattr(peer, "user_id", None)

            known = {key(p) for p in target.include_peers}
            for entity in entities:
                peer = await self.client.get_input_entity(entity)
                if key(peer) not in known:
                    target.include_peers.append(peer)
                    known.add(key(peer))
            await self.client(UpdateDialogFilterRequest(id=target.id, filter=target))
            if self._folder_id != target.id:
                self._folder_id = target.id
                self.set("folder_id", target.id)
        except Exception as e:
            logger.warning("Folder update failed: %s", e)

    async def _status(self, message, attempts: int = 3):
        for attempt in range(1, attempts + 1):
            try:
                peer = await message.get_input_chat()
                return await self.client(GetGiveawayInfoRequest(peer=peer, msg_id=message.id))
            except Exception as e:
                logger.warning("Giveaway status %s/%s failed (%s/%s): %s", message.chat_id, message.id, attempt, attempts, e)
                if attempt < attempts:
                    await asyncio.sleep(attempt * 2)
        return None

    def _evaluate(self, status, media):
        """Returns (verdict, reason): ok, final or retry"""
        s = self.strings
        if getattr(status, "participating", False):
            return "ok", ""
        early = getattr(status, "joined_too_early_date", None)
        if early:
            return "final", s["r_early"].format(early.strftime("%Y-%m-%d %H:%M UTC"))
        if getattr(status, "admin_disallowed_chat_id", None):
            return "final", s["r_admin"]
        country = getattr(status, "disallowed_country", None)
        if country:
            return "final", s["r_country"].format(country)
        if getattr(status, "preparing_results", False):
            return "final", s["r_preparing"]
        if getattr(media, "only_new_subscribers", False):
            return "final", s["r_new_only"]
        return "retry", s["r_generic"]

    # ---------- processing ----------

    def _retry_later(self, chat_id: int, message_id: int, delay: int, attempt: int):
        uid = f"{chat_id}_{message_id}"
        if attempt > MAX_ATTEMPTS:
            logger.warning("Giveaway %s was not processed after %s attempts", uid, MAX_ATTEMPTS)
            self._skip_add(uid)
            return
        if uid in self._retry:
            return

        async def run():
            await asyncio.sleep(delay)
            self._retry.pop(uid, None)
            try:
                message = await self.client.get_messages(chat_id, ids=message_id)
                media = getattr(message, "media", None)
                if isinstance(media, MessageMediaGiveaway):
                    await self._process(message, media, attempt)
            except Exception as e:
                logger.warning("Retry of giveaway %s failed: %s", uid, e)

        self._retry[uid] = self.create_task(run())

    async def _process(self, message, media, attempt: int = 1) -> bool:
        async with self._lock:
            return await self._process_locked(message, media, attempt)

    async def _process_locked(self, message, media, attempt: int) -> bool:
        chat_id = message.chat_id
        uid = f"{chat_id}_{message.id}"
        if uid in self._giveaways or uid in self._skip:
            return False

        fingerprint = self._fingerprint(media)
        if any(rec.get("fp") == fingerprint for rec in self._giveaways.values()):
            self._skip_add(uid)
            return False

        stars = int(getattr(media, "stars", 0) or 0)
        months = int(getattr(media, "months", 0) or 0)
        target = self.config["target_giveaways"]
        if (target == "Premium" and not months) or (target == "Stars" and not stars):
            return False
        if not getattr(media, "until_date", None):
            return False
        until = int(media.until_date.timestamp())
        if until <= time.time():
            return False

        leave_at = until + int(self.config["leave_after_hours"]) * 3600
        entities, unresolved = [], []
        for channel_id in list(getattr(media, "channels", None) or []):
            entity = await self._entity(channel_id)
            if entity is None:
                unresolved.append(channel_id)
            else:
                entities.append((channel_id, entity))

        new_count = 0
        for channel_id, entity in entities:
            key = str(channel_id)
            tracked = self._channels.get(key)
            if tracked and tracked.get("state") == "joined":
                tracked["leave_at"] = max(tracked.get("leave_at", 0), leave_at)
                continue
            if await self._join(entity) != "joined":
                continue
            new_count += 1
            self._channels[key] = {
                "title": getattr(entity, "title", "") or key,
                "state": "joined",
                "joined_at": int(time.time()),
                "leave_at": leave_at,
                "fails": 0,
            }
            await self._tidy(entity)
            await asyncio.sleep(self.config["join_delay"])
        self._save_channels()
        await self._add_to_folder([entity for _, entity in entities])

        if unresolved:
            self._retry_later(chat_id, message.id, 30, attempt + 1)
            return False

        await asyncio.sleep(2)
        status = await self._status(message)
        if status is None:
            self._retry_later(chat_id, message.id, 30, attempt + 1)
            return False

        verdict, reason = self._evaluate(status, media)
        rec = {
            "chat_id": chat_id,
            "msg_id": message.id,
            "link": await self._link(message),
            "stars": stars,
            "months": months,
            "quantity": int(getattr(media, "quantity", 0) or 0),
            "until": until,
            "fp": fingerprint,
            "channels": [cid for cid, _ in entities],
            "joined_at": int(time.time()),
            "result": None,
        }
        if verdict == "ok":
            self._giveaways[uid] = rec
            self._save_giveaways()
            await self._notify(lambda rich: self._card_new(rec, new_count, rich))
            return True
        if verdict == "final" or attempt >= MAX_ATTEMPTS:
            self._skip_add(uid)
            await self._notify(lambda rich: self._card_fail(rec, reason))
        else:
            self._retry_later(chat_id, message.id, 45, attempt + 1)
        return False

    # ---------- results and leaving ----------

    async def _result_info(self, rec: dict):
        try:
            peer = await self.client.get_input_entity(rec["chat_id"])
            info = await self.client(GetGiveawayInfoRequest(peer=peer, msg_id=rec["msg_id"]))
        except Exception as e:
            logger.debug("Giveaway result request failed: %s", e)
            return None
        return info if isinstance(info, GiveawayInfoResults) else None

    async def _check_results(self):
        now = time.time()
        give_up = int(self.config["leave_after_hours"]) * 3600 + RESULT_GIVE_UP
        changed = False
        for rec in list(self._giveaways.values()):
            if rec.get("result") or rec["until"] > now:
                continue
            if now > rec["until"] + give_up:
                rec["result"] = "unknown"
                changed = True
                continue
            info = await self._result_info(rec)
            if info is None:
                continue
            rec["result"] = "win" if info.winner else "lose"
            rec["prize_stars"] = int(getattr(info, "stars_prize", 0) or 0)
            changed = True
            if info.winner:
                await self._notify(lambda rich, rec=rec: self._card_win(rec))
            await asyncio.sleep(1)
        if changed:
            self._save_giveaways()

    async def _leave_due(self):
        if not self.config["auto_leave"]:
            return
        now = time.time()
        for key, channel in list(self._channels.items()):
            if channel.get("state") != "joined" or channel.get("leave_at", 0) > now:
                continue
            if await self._leave(int(key)):
                channel["state"] = "left"
                channel["left_at"] = int(now)
            else:
                channel["fails"] = channel.get("fails", 0) + 1
                if channel["fails"] >= FAIL_LIMIT:
                    channel["state"] = "failed"
            self._save_channels()
            await asyncio.sleep(self.config["join_delay"])

    @loader.loop(interval=600, autostart=True)
    async def maintenance(self):
        try:
            await self._check_results()
            await self._leave_due()
        except Exception as e:
            logger.warning("Maintenance failed: %s", e)

    # ---------- commands ----------

    @loader.command(
        ru_doc="включить или выключить авто-участие в розыгрышах",
        uk_doc="увімкнути або вимкнути авто-участь у розіграшах",
        de_doc="Automatische Teilnahme an Gewinnspielen ein- oder ausschalten",
        ja_doc="プレゼント企画への自動参加を切り替える",
    )
    async def gw(self, message: Message):
        """Toggle auto participation in giveaways"""
        enabled = not self.get("enabled", False)
        if enabled and self._join_blocked():
            return await self._say(message, self._limiter_card)
        self.set("enabled", enabled)
        s = self.strings
        await self._say(
            message,
            lambda rich: {
                "emoji": "on" if enabled else "off",
                "title": s["gw_on"] if enabled else s["gw_off"],
                "lines": [s["gw_on_hint"] if enabled else s["gw_off_hint"]],
            },
        )

    @loader.command(
        ru_doc="проверить историю чатов и найти пропущенные розыгрыши",
        uk_doc="перевірити історію чатів і знайти пропущені розіграші",
        de_doc="Chatverlauf nach verpassten Gewinnspielen durchsuchen",
        ja_doc="チャット履歴から見逃した企画を探す",
    )
    async def gwscan(self, message: Message):
        """Scan chat history for missed giveaways"""
        if self._join_blocked():
            return await self._say(message, self._limiter_card)
        if self._scanning:
            return await self._say(message, lambda rich: {"emoji": "warn", "title": self.strings["scan_busy"]})
        self._scanning = True
        self._scan_halt = False
        self._edit_errors = 0
        self._scan_rich = False
        self._scan_last = None
        self._scan_closed = False
        self._scan_task = self.create_task(self._scan_job(message))

    async def _scan_job(self, message):
        try:
            await self._run_scan(message)
        except Exception:
            logger.exception("Giveaway scan failed")
        finally:
            self._scanning = False
            self._scan_msg = None
            self._scan_state = None

    async def _stop_scan(self, call):
        self._scan_halt = True
        await call.answer(self.strings["scan_stopping"])

    def _scan_card(self, state: dict, phase: str):
        s = self.strings
        emoji = {"run": "search", "done": "ok", "stopped": "warn"}[phase]
        title = s[{"run": "scan_run", "done": "scan_done", "stopped": "scan_stopped"}[phase]]

        def build(rich: bool) -> dict:
            checked, total = state["checked"], state["total"]
            filled = 0 if not total else int(10 * checked / total)
            percent = 0 if not total else int(100 * checked / total)
            found = state["found"]
            card = {
                "emoji": emoji,
                "title": title,
                "lines": [f"<code>{'█' * filled}{'░' * (10 - filled)} {percent}%</code>"],
                "rows": [(s["scan_chats"], f"{checked} / {total}"), (s["scan_found"], str(len(found)))],
            }
            if phase == "run" and state["current"]:
                card["lines"].append(s["scan_now"].format(utils.escape_html(state["current"])))
            if phase == "run":
                card["buttons"] = [(s["btn_stop"], "gw:stop", "primary")]
            if found:
                shown = found[-20:]
                card["sections"] = [
                    (s["scan_results"].format(len(found)), [self._item(r, rich) for r in shown])
                ]
            return card

        return build

    async def _close_scan(self, call):
        self._scan_halt = True
        self._scan_closed = True
        await call.delete()

    def _close_button(self):
        return {"text": self.strings["btn_close"], "callback": self._close_scan, "style": "danger"}

    def _progress_markup(self):
        return [
            [{"text": self.strings["btn_stop"], "callback": self._stop_scan, "style": "primary"}],
            [self._close_button()],
        ]

    async def _scan_form(self, message, build):
        """Rich progress form, plain inline form if Telegram rejects rich"""
        if not self.inline.init_complete:
            return None
        try:
            form = await self.inline.form(
                "Rich message",
                message,
                rich_message=self._render(build(True), True),
                reply_markup=[[self._close_button()]],
                ttl=86400,
                silent=True,
            )
            if form:
                self._scan_rich = True
                return form
        except Exception as e:
            logger.warning("Rich scan form failed: %s", e)
        try:
            form = await self.inline.form(
                self._render(build(False), False),
                message,
                reply_markup=self._progress_markup(),
                ttl=86400,
                silent=True,
            )
        except Exception as e:
            logger.warning("Scan form failed: %s", e)
            return None
        return form or None

    async def _scan_edit(self, form, build):
        try:
            if self._scan_rich:
                html = self._render(build(True), True)
                if html == self._scan_last:
                    return
                self._scan_last = html
                ok = await form.edit(rich_message=html, reply_markup=[[self._close_button()]])
            else:
                ok = await form.edit(self._render(build(False), False), reply_markup=self._progress_markup())
            if ok is False:
                self._scan_last = None
                self._edit_errors = getattr(self, "_edit_errors", 0) + 1
                if self._edit_errors <= 3:
                    logger.warning(
                        "Scan progress edit returned False (inline_message_id=%s)",
                        getattr(form, "inline_message_id", None),
                    )
        except Exception:
            self._edit_errors = getattr(self, "_edit_errors", 0) + 1
            if self._edit_errors <= 3:
                logger.exception("Scan progress could not be edited")

    @loader.callback_handler()
    async def gw_callback_handler(self, call: InlineCall):
        if call.data != "gw:stop":
            return
        self._scan_halt = True
        await call.answer(self.strings["scan_stopping"])

    async def _scan_ticker(self, state: dict):
        while True:
            if self._scan_msg:
                await self._scan_edit(self._scan_msg, self._scan_card(state, "run"))
            await asyncio.sleep(PROGRESS_EVERY)

    async def _run_scan(self, message):
        state = {"checked": 0, "total": 0, "current": self.strings["scan_loading"], "found": []}
        self._scan_state = state
        self._scan_msg = await self._scan_form(message, self._scan_card(state, "run"))
        ticker = self.create_task(self._scan_ticker(state))
        dialogs = []
        async for dialog in self.client.iter_dialogs():
            if self._scan_halt:
                break
            if dialog.is_channel or dialog.is_group:
                dialogs.append(dialog)
                state["total"] = len(dialogs)
                state["current"] = dialog.name or str(dialog.id)
        state["total"] = len(dialogs)
        state["current"] = ""
        limit = self.config["scan_history_limit"]
        for dialog in dialogs:
            if self._scan_halt:
                break
            state["current"] = dialog.name or str(dialog.id)
            try:
                async for msg in self.client.iter_messages(dialog.entity, limit=limit):
                    if self._scan_halt:
                        break
                    media = getattr(msg, "media", None)
                    if isinstance(media, MessageMediaGiveaway) and await self._process(msg, media):
                        state["found"].append(self._giveaways[f"{msg.chat_id}_{msg.id}"])
            except FloodWaitError as e:
                await asyncio.sleep(min(e.seconds, 300))
            except Exception as e:
                logger.debug("Scan of %s failed: %s", dialog.id, e)
            state["checked"] += 1
            await asyncio.sleep(0)
        ticker.cancel()
        if self._scan_closed:
            return
        build = self._scan_card(state, "stopped" if self._scan_halt else "done")
        form, self._scan_msg = self._scan_msg, None
        if form:
            try:
                if self._scan_rich:
                    await form.edit(rich_message=self._render(build(True), True), reply_markup=[[self._close_button()]])
                else:
                    await form.edit(self._render(build(False), False), reply_markup=[[self._close_button()]])
                return
            except Exception as e:
                logger.warning("Could not show the scan result in the form: %s", e)
        try:
            await self._say(message, build)
        except Exception as e:
            logger.warning("Could not edit the command message: %s", e)
            await self.client.send_message(message.chat_id, self._render(build(False), False))

    @loader.command(
        ru_doc="показать активные розыгрыши",
        uk_doc="показати активні розіграші",
        de_doc="aktive Gewinnspiele anzeigen",
        ja_doc="進行中の企画を表示する",
    )
    async def gwst(self, message: Message):
        """Show active giveaways"""
        s = self.strings
        now = time.time()
        active = sorted((r for r in self._giveaways.values() if r["until"] > now), key=lambda r: r["until"])
        if not active:
            return await self._say(message, lambda rich: {"emoji": "info", "title": s["st_empty"]})
        await self._say(
            message,
            lambda rich: {
                "emoji": "bell",
                "title": s["st_title"],
                "lines": [s["st_count"].format(len(active))],
                "items": [self._item(rec, rich) for rec in active],
            },
        )

    @loader.command(
        ru_doc="статистика: участия, победы и каналы",
        uk_doc="статистика: участь, перемоги та канали",
        de_doc="Statistik: Teilnahmen, Gewinne und Kanäle",
        ja_doc="統計: 参加、当選、チャンネル",
    )
    async def gwstats(self, message: Message):
        """Show statistics and history"""
        s = self.strings
        now = time.time()
        records = list(self._giveaways.values())
        channels = list(self._channels.values())
        wins = sum(1 for r in records if r.get("result") == "win")
        active = sum(1 for r in records if r["until"] > now)
        waiting = sum(1 for r in records if r["until"] <= now and not r.get("result"))
        subscribed = sum(1 for c in channels if c.get("state") == "joined")
        left = sum(1 for c in channels if c.get("state") == "left")

        def build(rich: bool) -> dict:
            card = {
                "emoji": "stats",
                "title": s["stats_title"],
                "rows": [
                    (s["stat_joined"], str(len(records))),
                    (s["stat_wins"], str(wins)),
                    (s["stat_total"], str(len(channels))),
                    (s["stat_now"], str(subscribed)),
                    (s["stat_left"], str(left)),
                    (s["stat_active"], str(active)),
                    (s["stat_wait"], str(waiting)),
                ],
            }
            return card

        await self._say(message, build)

    @loader.watcher("only_messages")
    async def watcher(self, message: Message):
        if not self.get("enabled", False) or self._join_blocked():
            return
        media = getattr(message, "media", None)
        if isinstance(media, MessageMediaGiveaway):
            await self._process(message, media)
