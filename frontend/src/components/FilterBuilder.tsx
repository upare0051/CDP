import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus, Trash2, GripVertical, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { 
  getSegmentSchema, 
  FilterCondition, 
  FilterConfig, 
  SegmentField, 
  SegmentOperator 
} from '@/lib/api';
import Button from '@/components/Button';
import Select from '@/components/Select';
import Input from '@/components/Input';

interface FilterBuilderProps {
  value: FilterConfig;
  onChange: (config: FilterConfig) => void;
  className?: string;
}

const FIELD_CATEGORIES = [
  { id: 'contact', label: 'Contact' },
  { id: 'profile', label: 'Profile' },
  { id: 'location', label: 'Location' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'engagement', label: 'Engagement' },
  { id: 'preferences', label: 'Preferences' },
  { id: 'marketing', label: 'Marketing' },
];

export default function FilterBuilder({ value, onChange, className }: FilterBuilderProps) {
  const { data: schema } = useQuery({
    queryKey: ['segment-schema'],
    queryFn: getSegmentSchema,
    staleTime: Infinity,
  });

  const addFilter = () => {
    const newFilter: FilterCondition = {
      field: schema?.fields[0]?.name || '',
      operator: 'equals',
      value: '',
    };
    onChange({
      ...value,
      filters: [...value.filters, newFilter],
    });
  };

  const updateFilter = (index: number, updates: Partial<FilterCondition>) => {
    const newFilters = [...value.filters];
    newFilters[index] = { ...newFilters[index], ...updates };
    
    // Reset value when field or operator changes
    if (updates.field || updates.operator) {
      const field = schema?.fields.find(f => f.name === (updates.field || newFilters[index].field));
      if (field && updates.operator) {
        // Reset value for operators that don't need one
        if (['is_empty', 'is_not_empty', 'is_true', 'is_false'].includes(updates.operator)) {
          newFilters[index].value = null;
        }
      }
    }
    
    onChange({ ...value, filters: newFilters });
  };

  const removeFilter = (index: number) => {
    onChange({
      ...value,
      filters: value.filters.filter((_, i) => i !== index),
    });
  };

  const toggleLogic = () => {
    onChange({
      ...value,
      logic: value.logic === 'AND' ? 'OR' : 'AND',
    });
  };

  const getFieldType = (fieldName: string): string => {
    return schema?.fields.find(f => f.name === fieldName)?.type || 'string';
  };

  const getOperatorsForField = (fieldName: string): SegmentOperator[] => {
    const fieldType = getFieldType(fieldName);
    return schema?.operators_by_type[fieldType] || [];
  };

  // Group fields by category
  const fieldsByCategory = FIELD_CATEGORIES.map(cat => ({
    ...cat,
    fields: schema?.fields.filter(f => f.category === cat.id) || [],
  })).filter(cat => cat.fields.length > 0);

  return (
    <div className={cn("space-y-4", className)}>
      {/* Logic Toggle */}
      {value.filters.length > 1 && (
        <div className="flex items-center gap-3 pb-3 border-b border-gray-200 dark:border-gray-800">
          <span className="text-sm text-gray-500 dark:text-gray-400">Match</span>
          <button
            onClick={toggleLogic}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
              value.logic === 'AND'
                ? "bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
            )}
          >
            ALL
          </button>
          <button
            onClick={toggleLogic}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
              value.logic === 'OR'
                ? "bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
            )}
          >
            ANY
          </button>
          <span className="text-sm text-gray-500 dark:text-gray-400">of the following conditions</span>
        </div>
      )}

      {/* Filter Rows */}
      <div className="space-y-3">
        {value.filters.map((filter, index) => (
          <FilterRow
            key={index}
            filter={filter}
            index={index}
            fieldsByCategory={fieldsByCategory}
            getOperatorsForField={getOperatorsForField}
            getFieldType={getFieldType}
            onUpdate={(updates) => updateFilter(index, updates)}
            onRemove={() => removeFilter(index)}
            showLogicLabel={index > 0}
            logic={value.logic}
          />
        ))}
      </div>

      {/* Empty State */}
      {value.filters.length === 0 && (
        <div className="py-8 text-center border-2 border-dashed border-gray-200 dark:border-gray-800 rounded-xl">
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            No filters added yet. Add filters to define an audience.
          </p>
          <Button onClick={addFilter} variant="secondary" size="sm">
            <Plus className="w-4 h-4" />
            Add First Filter
          </Button>
        </div>
      )}

      {/* Add Filter Button */}
      {value.filters.length > 0 && (
        <Button onClick={addFilter} variant="ghost" size="sm" className="w-full border border-dashed border-gray-300 dark:border-gray-700">
          <Plus className="w-4 h-4" />
          Add Filter
        </Button>
      )}
    </div>
  );
}

interface FilterRowProps {
  filter: FilterCondition;
  index: number;
  fieldsByCategory: { id: string; label: string; fields: SegmentField[] }[];
  getOperatorsForField: (field: string) => SegmentOperator[];
  getFieldType: (field: string) => string;
  onUpdate: (updates: Partial<FilterCondition>) => void;
  onRemove: () => void;
  showLogicLabel: boolean;
  logic: 'AND' | 'OR';
}

function FilterRow({
  filter,
  index,
  fieldsByCategory,
  getOperatorsForField,
  getFieldType,
  onUpdate,
  onRemove,
  showLogicLabel,
  logic,
}: FilterRowProps) {
  const operators = getOperatorsForField(filter.field);
  const fieldType = getFieldType(filter.field);
  const currentOperator = filter.operator;
  
  // Determine if value input is needed
  const needsValue = !['is_empty', 'is_not_empty', 'is_true', 'is_false'].includes(currentOperator);
  const needsSecondValue = currentOperator === 'between';

  // Build grouped field options
  const fieldOptions: { value: string; label: string; disabled?: boolean }[] =
    fieldsByCategory.flatMap((cat) => [
      { value: `__group_${cat.id}`, label: `── ${cat.label} ──`, disabled: true },
      ...cat.fields.map((f) => ({ value: f.name, label: f.label })),
    ]);

  return (
    <div className="flex items-center gap-2 animate-fade-in">
      {/* Logic Label */}
      {showLogicLabel && (
        <span className="w-12 text-xs font-medium text-gray-400 dark:text-gray-500 text-center">
          {logic}
        </span>
      )}
      {!showLogicLabel && index === 0 && (
        <span className="w-12 text-xs font-medium text-gray-400 dark:text-gray-500 text-center">
          Where
        </span>
      )}

      {/* Filter Card */}
      <div className="flex-1 flex items-center gap-2 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
        {/* Drag Handle */}
        <GripVertical className="w-4 h-4 text-gray-300 dark:text-gray-600 cursor-grab" />

        {/* Field Select */}
        <select
          value={filter.field}
          onChange={(e) => onUpdate({ field: e.target.value })}
          className={cn(
            "flex-1 min-w-[140px] px-3 py-2 text-sm rounded-lg",
            "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700",
            "text-gray-900 dark:text-gray-100",
            "focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
          )}
        >
          {fieldOptions.map((opt) => (
            <option 
              key={opt.value} 
              value={opt.value} 
              disabled={opt.disabled}
              className={opt.disabled ? 'font-medium text-gray-500' : ''}
            >
              {opt.label}
            </option>
          ))}
        </select>

        {/* Operator Select */}
        <select
          value={filter.operator}
          onChange={(e) => onUpdate({ operator: e.target.value })}
          className={cn(
            "min-w-[160px] px-3 py-2 text-sm rounded-lg",
            "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700",
            "text-gray-900 dark:text-gray-100",
            "focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
          )}
        >
          {operators.map((op) => (
            <option key={op.value} value={op.value}>
              {op.label}
            </option>
          ))}
        </select>

        {/* Value Input */}
        {needsValue && (
          <ValueInput
            fieldType={fieldType}
            operator={currentOperator}
            value={filter.value}
            value2={filter.value2}
            onChange={(val, val2) => onUpdate({ value: val, value2: val2 })}
            needsSecondValue={needsSecondValue}
          />
        )}

        {/* Remove Button */}
        <button
          onClick={onRemove}
          className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
          title="Remove filter"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

interface ValueInputProps {
  fieldType: string;
  operator: string;
  value: any;
  value2?: any;
  onChange: (value: any, value2?: any) => void;
  needsSecondValue: boolean;
}

function ValueInput({ fieldType, operator, value, value2, onChange, needsSecondValue }: ValueInputProps) {
  const getInputType = () => {
    if (fieldType === 'number') return 'number';
    if (fieldType === 'date') return 'date';
    if (['last_n_days', 'next_n_days'].includes(operator)) return 'number';
    return 'text';
  };

  const inputType = getInputType();
  const placeholder = ['last_n_days', 'next_n_days'].includes(operator) ? 'Days' : 'Value';

  return (
    <div className="flex items-center gap-2">
      <input
        type={inputType}
        value={value || ''}
        onChange={(e) => onChange(e.target.value, value2)}
        placeholder={placeholder}
        className={cn(
          "w-32 px-3 py-2 text-sm rounded-lg",
          "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700",
          "text-gray-900 dark:text-gray-100 placeholder:text-gray-400",
          "focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
        )}
      />
      
      {needsSecondValue && (
        <>
          <span className="text-gray-400 text-sm">and</span>
          <input
            type={inputType}
            value={value2 || ''}
            onChange={(e) => onChange(value, e.target.value)}
            placeholder={placeholder}
            className={cn(
              "w-32 px-3 py-2 text-sm rounded-lg",
              "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700",
              "text-gray-900 dark:text-gray-100 placeholder:text-gray-400",
              "focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
            )}
          />
        </>
      )}
    </div>
  );
}

// Compact preview of filters
export function FilterPreview({ config }: { config: FilterConfig }) {
  if (config.filters.length === 0) {
    return <span className="text-gray-400 dark:text-gray-500">No filters</span>;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {config.filters.slice(0, 3).map((filter, idx) => (
        <span key={idx} className="flex items-center gap-1">
          {idx > 0 && (
            <span className="text-xs text-gray-400 dark:text-gray-500 px-1">{config.logic}</span>
          )}
          <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-800 rounded text-gray-600 dark:text-gray-400">
            {filter.field} {filter.operator} {filter.value}
          </span>
        </span>
      ))}
      {config.filters.length > 3 && (
        <span className="text-xs text-gray-400 dark:text-gray-500">
          +{config.filters.length - 3} more
        </span>
      )}
    </div>
  );
}
