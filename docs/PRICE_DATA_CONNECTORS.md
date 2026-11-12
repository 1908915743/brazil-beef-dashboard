# 价格快报数据接入说明

## 当前状态
前端已经读取仓库根目录的 `wholesale_price.json`。本分支增加每日定时工作流和数据采集脚本；缺少接口配置时只显示“待接入”，不伪造行情。真实数据尚未接入。

## 目标指标
- 农业农村部：全国牛肉平均批发价格，单位元/公斤。
- Scot Consultoria：Carcaça Casada，单位R$/kg。

## 需要申请的正式数据通道
1. 向农业农村部平台运营方申请可供企业自动化读取的接口、数据文件或书面许可，并确认该指标是否就是全国牛肉平均批发价格及其发布日期、统计口径。
2. 向 Scot Consultoria 申请企业展示许可及 API/数据订阅，确认 Carcaça Casada 的地区、税费、报价类型、单位和更新时间。
3. 不要把网页登录后的内部请求地址当作公开 API，也不要绕过登录、付费或访问控制。

## GitHub Secrets
取得授权接口后，在仓库 Settings → Secrets and variables → Actions 添加：
- `MOA_WHOLESALE_API_URL`
- `SCOT_CARCACA_API_URL`

每个 URL 应是经授权的 HTTPS JSON 接口。当前适配器要求接口返回如下结构：
```json
{
  "item": {
    "id": "china_beef_wholesale",
    "value": 58.25,
    "unit": "元/公斤",
    "quote_date": "2026-11-12",
    "change_value": 0.15,
    "change_pct": 0.26
  }
}
```
Scot 的 `id` 使用 `brazil_carcaca_casada`，单位为 `R$/kg`。数值和日期必须来自真实授权来源。取得官方接口文档或样例 JSON 后，还需要按其真实字段结构调整适配器并联调。

## 更新频率
GitHub Actions 每天北京时间16:30运行一次，也可在 Actions 页面手动运行。该频率是每日定时检查，不代表来源发布数据后立即推送；如需“有新数据就更新”，要看数据方是否提供 webhook/发布通知，或提高轮询频率。
