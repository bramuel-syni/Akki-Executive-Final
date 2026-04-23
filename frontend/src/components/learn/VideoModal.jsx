import React from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ExternalLink, User } from "lucide-react";

/**
 * VideoModal — embeds a YouTube video in an AKKI-styled dialog.
 * Props: open, onOpenChange, video (with youtube_id, title, speaker, source_name, source_url)
 */
export default function VideoModal({ open, onOpenChange, video }) {
  if (!video) return null;
  const src = `https://www.youtube.com/embed/${video.youtube_id}?autoplay=1&rel=0&modestbranding=1`;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[960px] p-0 bg-white border border-[var(--rule)] rounded-lg overflow-hidden"
        data-testid="video-modal"
      >
        <DialogTitle className="sr-only">{video.title}</DialogTitle>

        <div className="w-full aspect-video bg-black">
          {open && (
            <iframe
              title={video.title}
              src={src}
              width="100%"
              height="100%"
              frameBorder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              data-testid="video-iframe"
            />
          )}
        </div>

        <div className="p-6 bg-[var(--cream)]">
          <p className="akki-type-badge mb-2">{video.kicker}</p>
          <h2 className="akki-serif text-[22px] leading-snug text-[var(--ink)] mb-3 font-normal">
            {video.title}
          </h2>
          <p className="akki-serif text-[15px] text-[var(--deep)] leading-relaxed italic mb-4">
            {video.summary}
          </p>
          <div className="flex items-center justify-between text-[12px] text-[var(--muted)] pt-3 border-t border-[var(--rule)]">
            <span className="inline-flex items-center gap-1.5">
              <User className="w-3 h-3" /> {video.speaker}
            </span>
            <a
              href={video.source_url}
              target="_blank"
              rel="noreferrer"
              className="akki-gesture"
              data-testid="video-source-link"
            >
              Open on {video.source_name} <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
