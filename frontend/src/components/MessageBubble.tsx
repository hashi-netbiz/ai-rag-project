import React from 'react';
import SourceCitation from './SourceCitation';
import { Source } from '../services/api';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

export default function MessageBubble({ role, content, sources }: Props) {
  const isUser = role === 'user';
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: '12px',
    }}>
      <div style={{
        maxWidth: '75%',
        background: isUser ? '#0078d4' : '#f3f4f6',
        color: isUser ? '#fff' : '#1f2937',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        padding: '10px 14px',
        boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
      }}>
        <p style={{ margin: 0, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{content}</p>
        {sources && sources.length > 0 && (
          <div style={{ marginTop: '8px' }}>
            {sources.map((s, i) => (
              <SourceCitation key={i} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
