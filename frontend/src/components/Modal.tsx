import { ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export default function Modal({ isOpen, onClose, title, children, size = 'md' }: ModalProps) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    
    if (isOpen) {
      document.addEventListener('keydown', handleEsc);
      document.body.style.overflow = 'hidden';
    }
    
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 dark:bg-black/70" onClick={onClose} />
      
      {/* Modal */}
      <div
        className={cn(
          'relative w-full border border-alo-mercury bg-white shadow-lg dark:border-neutral-800 dark:bg-black',
          'animate-fade-in',
          sizes[size]
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-alo-mercury px-6 py-4 dark:border-neutral-800">
          <h2 className="font-tag text-xs font-semibold uppercase tracking-[0.14em] text-black dark:text-white">{title}</h2>
          <button
            type="button"
            aria-label="Close modal"
            onClick={onClose}
            className="p-2 text-gray-500 transition-colors hover:bg-alo-smoke hover:text-black dark:text-neutral-400 dark:hover:bg-neutral-900 dark:hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-6 max-h-[70vh] overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
