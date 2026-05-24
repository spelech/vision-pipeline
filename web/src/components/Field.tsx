import React from 'react';

interface FieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
}

export function Field({ label, value, onChange }: FieldProps) {
  const id = React.useId();
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="label-apple">{label}</label>
      <input 
        id={id}
        className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:outline-none" 
        value={value || ''} 
        onChange={(e) => onChange(e.target.value)} 
      />
    </div>
  );
}
