// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { Youtube, Tv } from 'lucide-react';

/**
 * FeedImage - 订阅图标渲染
 * 有图显示图；无图或加载失败时按订阅类型显示平台图标兜底
 * （youtube → YouTube 红播放键；bilibili → B站粉小电视；其余 → placeholder）
 */
const FALLBACKS = {
  youtube: { Icon: Youtube, bg: 'bg-red-600' },
  bilibili: { Icon: Tv, bg: 'bg-[#fb7299]' },
};

const FeedImage = ({ feed, className = '' }) => {
  const [failed, setFailed] = useState(false);
  const fallback = FALLBACKS[feed?.type];

  if (!feed?.image || failed) {
    if (fallback) {
      const { Icon, bg } = fallback;
      return (
        <div className={`${className} ${bg} flex items-center justify-center`}>
          <Icon className="h-[45%] w-[45%] text-white" />
        </div>
      );
    }
    return (
      <img
        src="/placeholder.png"
        alt={feed?.title || ''}
        className={className}
      />
    );
  }

  return (
    <img
      src={feed.image}
      alt={feed.title}
      className={className}
      onError={() => setFailed(true)}
    />
  );
};

export default FeedImage;
