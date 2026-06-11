"""一次性种子数据脚本：将阶段二的演示数据写入数据库。

用法： python -m app.seed
"""

from app.database import SessionLocal
from app.models import Category, Demo

CATEGORIES = [
    {
        "name": "网站模板",
        "slug": "website-templates",
        "description": "企业官网、落地页等网站类 Demo",
        "demos": [
            {
                "name": "企业官网模板",
                "slug": "corporate-site",
                "description": "深色科技风企业官网首页模板",
                "thumbnail_path": None,
                "view_count": 128,
            },
            {
                "name": "产品落地页",
                "slug": "landing-page",
                "description": "面向新产品发布的高转化落地页",
                "thumbnail_path": "/thumbnails/landing-page.svg",
                "view_count": 256,
            },
        ],
    },
    {
        "name": "小程序 / App UI",
        "slug": "app-ui",
        "description": "移动端应用界面 Demo",
        "demos": [
            {
                "name": "电商购物 App",
                "slug": "ecommerce-app",
                "description": "商品列表、详情与购物车界面演示",
                "thumbnail_path": None,
                "view_count": 42,
            },
            {
                "name": "健身打卡 App",
                "slug": "fitness-tracker",
                "description": "运动记录与数据统计界面演示",
                "thumbnail_path": None,
                "view_count": 17,
            },
        ],
    },
    {
        "name": "数据可视化",
        "slug": "data-viz",
        "description": "图表与数据看板类 Demo",
        "demos": [
            {
                "name": "销售数据看板",
                "slug": "sales-dashboard",
                "description": "销售额、订单量等核心指标可视化看板",
                "thumbnail_path": "/thumbnails/sales-dashboard.svg",
                "view_count": 73,
            },
        ],
    },
]


def seed():
    db = SessionLocal()
    try:
        if db.query(Category).count() > 0:
            print("数据库中已有分类数据，跳过种子导入")
            return

        for sort_order, category_data in enumerate(CATEGORIES):
            category = Category(
                name=category_data["name"],
                slug=category_data["slug"],
                description=category_data["description"],
                sort_order=sort_order,
            )
            db.add(category)
            db.flush()

            for demo_sort_order, demo_data in enumerate(category_data["demos"]):
                db.add(
                    Demo(
                        name=demo_data["name"],
                        slug=demo_data["slug"],
                        category_id=category.id,
                        description=demo_data["description"],
                        thumbnail_path=demo_data["thumbnail_path"],
                        view_count=demo_data["view_count"],
                        sort_order=demo_sort_order,
                    )
                )

        db.commit()
        print("种子数据导入完成")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
