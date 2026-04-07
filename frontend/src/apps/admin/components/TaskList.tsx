import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import type { Task, TaskFilters } from '@/types';

interface TaskListProps {
  tasks: Task[];
  isLoading: boolean;
  filters: TaskFilters;
  onFilterChange: (filters: TaskFilters) => void;
  selectedTask: Task | null;
  onSelectTask: (task: Task) => void;
}

export function TaskList({
  tasks,
  isLoading,
  filters,
  onFilterChange,
  selectedTask,
  onSelectTask,
}: TaskListProps) {
  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'HIGH':
        return 'bg-red-100 text-red-700';
      case 'MEDIUM':
        return 'bg-yellow-100 text-yellow-700';
      case 'LOW':
        return 'bg-green-100 text-green-700';
      default:
        return 'bg-gray-100';
    }
  };

  return (
    <div className="bg-white rounded-lg border flex flex-col">
      <div className="p-3 border-b">
        <h2 className="font-semibold">任务队列</h2>
        <div className="text-sm text-gray-500">待审核: {tasks.length}</div>
      </div>

      <div className="p-3 border-b">
        <RadioGroup
          value={filters.riskLevel}
          onValueChange={(v) => onFilterChange({ riskLevel: v as TaskFilters['riskLevel'] })}
          className="flex gap-2"
        >
          {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((level) => (
            <div key={level} className="flex items-center space-x-1">
              <RadioGroupItem value={level} id={level} />
              <Label htmlFor={level} className="text-xs">
                {level === 'ALL' ? '全部' : level}
              </Label>
            </div>
          ))}
        </RadioGroup>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-2">
          {isLoading
            ? Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="p-3 border rounded">
                  <Skeleton className="h-4 w-20 mb-2" />
                  <Skeleton className="h-3 w-full" />
                </div>
              ))
            : tasks.length === 0
            ? <div className="p-4 text-center text-gray-500 text-sm">暂无待审核任务</div>
            : tasks.map((task) => (
                <div
                  key={task.audit_log_id}
                  onClick={() => onSelectTask(task)}
                  className={`p-3 border rounded cursor-pointer hover:bg-gray-50 ${
                    selectedTask?.audit_log_id === task.audit_log_id
                      ? 'border-brand-500 bg-brand-50'
                      : ''
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <span className="font-medium text-sm">#{task.audit_log_id}</span>
                    <Badge className={getRiskColor(task.risk_level)}>{task.risk_level}</Badge>
                  </div>
                  <div className="text-sm text-gray-600 mt-1">用户: {task.user_id}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    {new Date(task.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
        </div>
      </ScrollArea>
    </div>
  );
}
