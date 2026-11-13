from tasks.GameUi.page import Page, page_entertainment
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.RichMan.assets import RichManAssets


page_itachi_shop = Page(
    RichManAssets.I_ITACHI_SHOP_CHECK, key='page_itachi_shop',
    priority=75, category='rich_man',
)
# 商店入口会随底部菜单变化而移动，由图片规则定位后点击。
page_entertainment.connect(
    page_itachi_shop, RichManAssets.I_ITACHI_SHOP_ENTRY,
    key='page_entertainment->page_itachi_shop',
)
page_itachi_shop.connect(
    page_entertainment, GlobalGameAssets.I_UI_BACK_RED,
    key='page_itachi_shop->page_entertainment',
)
