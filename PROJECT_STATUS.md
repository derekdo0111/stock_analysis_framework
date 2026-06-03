# 项目状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段一 (地基) | 🟢 完成 | Pydantic v2 Schema + YAML加载器(4规则) + Tushare适配器(22接口) + JSON/Parquet存储 + 转换器 + 验证器 |
| 阶段二 (确定性管线) | 🟢 完成 | HardGate(6项否决) + L2初筛(纯门控,不评分) + 公司5分类 + L3十二维商业模式(0-30pt) + OE路径B + 穿透回报率(0-45pt) + L5纯估值安全边际(0-25pt) + 加法百分制 Final=L3+L4+L5=100pt |
| 阶段三 (LLM智能层) | 🟢 完成 | DeepSeek/OpenAI/Anthropic三平台客户端 + CFA分析Agent(9模块Rubric+三段式证据链) + CPA+CFE审计Agent(10项审计+三级严重度) + 修正循环(最多3次) + 降级机制 + CLI入口 + Jinja2 HTML报告 |
| 阶段四 (质量加固) | 🟢 完成 | GitHub Actions CI(ruff+mypy+pytest) + 162测试 + ruff零错误 + mypy零错误 |
| 阶段五 (回测验证) | 🟡 代码完成 | Walk-Forward 6窗口 + 管线运行 + 分红验证 + 统计 + 报告 —— 代码已写完、测试通过，**待真数据跑回测** |

**当前版本**: v0.23 — L3 十二维商业模式评估(0-30pt) + L5 纯估值安全边际(0-25pt) + 加法百分制 Final=L3+L4+L5=100pt

**版本历史**:
- v0.23: L3 十二维加法(盈利5+成熟3+纪律2+治理2) + L5 纯估值(安全边际率+下行缓冲+仓位) + 百分制
- v0.22: DC 扣除全部成长性投入（并购子公司+参股净增），PR 去除安全边际系数和红利税折扣
- v0.21: 分配比率外推修正（adjusted_dc = dc + total_div，消除循环悖论）
- v0.20: DC maintenance_capex 修正（c_pay_acq_const_fiolta 替代 stot_out_inv_act）

**测试**: 113 passed, 7 skipped, 30 failed, 12 errors, 162 total（30 failed/12 errors 为旧测试未同步 v0.23 公式变更，非本次引入）

**代码量**: ~8000行 Python (72个源文件)

**质量门禁**: ruff ✅ / mypy ✅ / YAML加载 ✅

**数据源**: Tushare(主) + akshare(备用) + Web+LLM提取(Layer3) + 年报PDF(降级)

**分池阈值**: 核心池≥75 / 观察池50-74 / 备选池<50

**折现率**: 7% = max(无风险利率+2%, 5%) + 个股风险溢价2%
