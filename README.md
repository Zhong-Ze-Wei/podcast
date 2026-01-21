# Podcast Manager

播客管理应用，支持 RSS 订阅、音频播放、语音转录和 AI 摘要生成。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 18 + Vite + TailwindCSS + i18next |
| 后端 | Flask + MongoDB |
| 转录 | Whisper (本地) / 外部转录源 |
| 摘要 | LLM API |

## 项目结构

```
podcast/
├── backend/                          # Flask 后端
│   ├── run.py                        # 启动入口
│   └── app/
│       ├── __init__.py               # 应用工厂, 数据库初始化, 索引创建
│       ├── config.py                 # 配置管理 (MongoDB, 媒体目录等)
│       │
│       ├── api/                      # REST API 接口层
│       │   ├── feeds.py              # 订阅源: 增删改查, 刷新, 收藏
│       │   ├── episodes.py           # 单集: 列表, 标星, 已读, 下载
│       │   ├── transcripts.py        # 转录: Whisper生成, 外部获取
│       │   ├── summaries.py          # 摘要: LLM生成
│       │   ├── tasks.py              # 异步任务状态
│       │   ├── stats.py              # 统计数据
│       │   └── utils.py              # 响应格式化, 分页
│       │
│       ├── models/                   # 数据模型 (MongoDB文档结构)
│       │   ├── feed.py               # 订阅源
│       │   ├── episode.py            # 单集
│       │   ├── transcript.py         # 转录文本
│       │   ├── summary.py            # AI摘要
│       │   └── task.py               # 异步任务
│       │
│       └── services/                 # 业务服务层
│           ├── rss_service.py        # RSS解析, 时长/图片/章节提取
│           ├── whisper_service.py    # Whisper本地转录
│           ├── transcript_fetcher.py # 外部转录获取
│           └── task_queue.py         # 线程池任务队列
│
├── frontend/                         # React 前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js                # Vite配置, API代理
│   ├── tailwind.config.js
│   │
│   └── src/
│       ├── main.jsx                  # 入口
│       ├── App.jsx                   # 主组件, 全局状态
│       ├── index.css                 # 全局样式
│       ├── i18n.js                   # 国际化配置
│       │
│       ├── services/
│       │   └── api.js                # Axios封装, 拦截器
│       │
│       ├── utils/
│       │   └── helpers.js            # 时间格式化, HTML解码等
│       │
│       ├── locales/
│       │   ├── zh.json               # 中文
│       │   └── en.json               # English
│       │
│       └── components/
│           ├── layout/
│           │   └── Sidebar.jsx       # 侧边栏导航, 订阅列表
│           │
│           ├── cards/
│           │   ├── FeedCard.jsx      # 订阅源卡片
│           │   └── EpisodeCard.jsx   # 单集卡片
│           │
│           ├── views/
│           │   ├── FeedDetailView.jsx    # 订阅源详情
│           │   ├── EpisodeDetailView.jsx # 单集详情 (转录/摘要)
│           │   ├── FavoritesView.jsx     # 收藏
│           │   ├── DownloadedView.jsx    # 已下载
│           │   └── TranscribedView.jsx   # 已转录
│           │
│           ├── player/
│           │   └── PlayerBar.jsx     # 底部播放器, 进度条
│           │
│           ├── tasks/
│           │   └── TaskPanel.jsx     # 右下角任务进度
│           │
│           └── common/
│               ├── StatusBadge.jsx
│               └── LanguageSwitcher.jsx
│
├── .gitignore
└── README.md
```

## 快速启动

### 环境要求
- Python 3.8+
- Node.js 18+
- MongoDB (端口 27017)

### 后端
```bash
cd backend
pip install -r requirements.txt
python run.py                    # 默认 http://localhost:5001
```

### 前端
```bash
cd frontend
npm install
npm run dev                      # 默认 http://localhost:3000
```

## 数据库集合

| 集合 | 说明 |
|------|------|
| feeds | 订阅源 |
| episodes | 单集 |
| transcripts | 转录文本 |
| summaries | AI摘要 |
| tasks | 异步任务 |

## API 概览

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/feeds` | 订阅列表 |
| POST | `/api/feeds` | 添加订阅 |
| GET | `/api/feeds/:id/episodes` | 订阅的单集 |
| POST | `/api/feeds/:id/refresh` | 刷新订阅 |
| GET | `/api/episodes` | 所有单集 |
| POST | `/api/episodes/:id/star` | 标星 |
| POST | `/api/transcripts/:id` | 生成转录 |
| POST | `/api/summaries/:id` | 生成摘要 |
| GET | `/api/tasks` | 任务列表 |

## 核心功能

- RSS订阅管理 (支持 Podcasting 2.0 标签)
- 内置播放器 (进度保存)
- 语音转录 (Whisper本地 / 外部源)
- AI摘要生成
- 中英文切换
