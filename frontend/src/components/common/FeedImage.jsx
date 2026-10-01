// -*- coding: utf-8 -*-
import React, { useState } from 'react';
import { Youtube, Tv } from 'lucide-react';

/**
 * FeedImage - 订阅图标渲染
 * 有图显示图；无图或加载失败时按订阅类型显示平台图标兜底
 * 本地封面与远程封面共用；失败时直接显示图标，不请求不存在的占位图片。
 */
const FALLBACKS = {
  youtube: { Icon: Youtube, bg: 'bg-red-600' },
  bilibili: { Icon: Tv, bg: 'bg-[#fb7299]' },
};

const FeedImage = ({ feed, fallbackImage, className = '' }) => {
  const [failedImages, setFailedImages] = useState([]);
  const image = [feed?.image, feed?.image_url, fallbackImage].find(url => url && !failedImages.includes(url));
  const fallback = FALLBACKS[feed?.type];

  if (!image) {
    if (fallback) {
      const { Icon, bg } = fallback;
      return (
        <div className={`${className} ${bg} flex items-center justify-center`}>
          <Icon className="h-[45%] w-[45%] text-white" />
        </div>
      );
    }
    const name = feed?.title || '播客';
    const initials = /[\u3400-\u9fff]/.test(name) ? name.slice(0, 2) : name.split(/\s+/).map(word => word[0]).join('').slice(0, 2).toUpperCase();
    return <span className={`${className} bg-zinc-800 text-zinc-400 inline-flex items-center justify-center`} role="img" aria-label={name}>{initials}</span>;
  }

  return (
    <img
      src={image}
      alt={feed.title}
      className={className}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailedImages(previous => [...previous, image])}
    />
  );
};

export default FeedImage;
