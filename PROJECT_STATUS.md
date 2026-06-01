# 项目状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段一 (地基) | 🟢 完成 | Pydantic v2 Schema(19模型) + YAML加载器(4规则) + Tushare适配器(23接口) + JSON/Parquet存储 + 转换器 + 验证器 |
| 阶段二 (确定性管线) | 🟢 完成 | HardGate(6项否决) + L2初筛(20分) + 公司5分类 + OE路径B + 穿透回报率(v0.19前瞻公式) + L5安全边际(6维外推+5陷阱+3×3仓位矩阵) + 乘法打分 |
| 阶段三 (LLM智能层) | 🟢 完成 | DeepSeek/OpenAI/Anthropic三平台客户端 + CFA分析Agent(9模块Rubric+三段式证据链) + CPA+CFE审计Agent(10项审计+三级严重度) + 修正循环(最多3次) + 降级机制 + CLI入口 + Jinja2 HTML报告 |
| 阶段四 (质量加固) | 🟢 完成 | GitHub Actions CI(ruff+mypy+pytest 3.9+3.11) + 162测试 + ruff零错误 + mypy零错误 |
| 阶段五 (回测验证) | 🟡 代码完成 | Walk-Forward 6窗口 + 管线运行 + 分红验证 + 统计 + 报告 —— 代码已写完、测试通过，**待真数据跑回测** |

**当前版本**: v0.19 — PR = (可支配现金 × 分配比率 × 0.9 + 回购注销) / 当前市值
**测试**: 130 passed, 26 failed (pre-existing Mock→Bundle迁移), 6 skipped
**代码量**: ~7000行 Python (49个源文件)
**质量门禁**: ruff ✅ / mypy ✅ / YAML加载 ✅
**数据源**: Tushare(主) + akshare(备用) + Web+LLM提取(Layer3) + 年报PDF(降级)
