# 价格快报数据接入说明

## 当前状态
前端读取仓库根目录的 `wholesale_price.json`。本分支已适配农业农村部 PFSC 每日报告列表请求，按报告日期从最新一页提取全国牛肉平均批发价格。Scot 数据仍待取得授权接口。

## 农业农村部数据
- 报告页面：https://pfsc.agri.cn/#/analysisReport
- 已在浏览器 Network 中观察到的报告列表请求：`POST https://pfsc.agri.cn/api/FarmDaily/list`
- 请求 JSON：`{"pageNum":1,"pageSize":10}`
- 预期返回结构：`content.list[]`，使用 `daylyDate` 作为报告日期、`animalConclusion` 提取“牛肉”价格。
- 脚本优先读取最新一页中日期最新且包含牛肉价格的报告；失败时保留上次有效值。

**重要：** 上述地址和字段来自网页运行时请求的观察，并不等于官方公开 API 或已授予企业自动化、商业展示权限。正式启用定时采集前，应向平台运营方确认网站条款、自动调用权限、频率限制及商业展示许可。不要绕过登录、付费或访问控制。

## Scot Consultoria
- 目标指标：Carcaça Casada，单位 R$/kg。
- 来源页面：https://www.scotconsultoria.com.br/cotacoes/
- 需要先申请企业展示许可及 API/数据订阅；取得真实响应样例后再开发对应适配器。

## 定时更新
GitHub Actions 设为每天 **北京时间15:00** 运行，对应 UTC 07:00（cron：`0 7 * * *`）。GitHub Actions 的定时任务可能有排队延迟，因此15:00是计划触发时间，不保证精确到分钟。也可在 Actions 页面手动运行。

## 配置
如官方确认允许使用其他正式接口，可在仓库 Settings → Secrets and variables → Actions 添加 `MOA_WHOLESALE_API_URL` 覆盖默认地址。Scot 接口取得授权后，再配置 `SCOT_CARCACA_API_URL`。不要将 Cookie、Authorization、Token 或账号密码写入代码或提交到仓库。
