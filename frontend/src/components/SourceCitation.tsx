import React from 'react';
import { Source } from '../services/api';

interface Props {
  source: Source;
}

export default function SourceCitation({ source }: Props) {
  const label = source.section ? `${source.file} › ${source.section}` : source.file;
  return (
    <span style={{
      display: 'inline-block',
      background: '#e8f4fd',
      border: '1px solid #b3d9f5',
      borderRadius: '12px',
      padding: '2px 10px',
      fontSize: '0.75rem',
      color: '#1a6ea0',
      margin: '2px 4px 2px 0',
    }}>
      📄 {label}
    </span>
  );
}
