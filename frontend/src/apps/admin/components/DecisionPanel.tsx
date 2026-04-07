import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import type { Task } from '@/types';

interface DecisionPanelProps {
  task: Task | null;
  onDecision: (auditLogId: number, action: 'APPROVE' | 'REJECT', comment: string) => void;
  isSubmitting: boolean;
}

export function DecisionPanel({ task, onDecision, isSubmitting }: DecisionPanelProps) {
  const [comment, setComment] = useState('');

  if (!task)
    return (
      <div className="bg-white rounded-lg border flex items-center justify-center">
        <div className="text-gray-400">请先选择任务</div>
      </div>
    );

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'HIGH':
        return <Badge className="bg-red-100 text-red-700">高风险</Badge>;
      case 'MEDIUM':
        return <Badge className="bg-yellow-100 text-yellow-700">中风险</Badge>;
      case 'LOW':
        return <Badge className="bg-green-100 text-green-700">低风险</Badge>;
      default:
        return <Badge>未知</Badge>;
    }
  };

  const handleApprove = () => {
    onDecision(task.audit_log_id, 'APPROVE', comment);
    setComment('');
  };

  const handleReject = () => {
    if (!comment.trim()) {
      alert('拒绝时必须填写审核备注');
      return;
    }
    onDecision(task.audit_log_id, 'REJECT', comment);
    setComment('');
  };

  return (
    <div className="bg-white rounded-lg border flex flex-col">
      <div className="p-3 border-b">
        <h2 className="font-semibold">决策面板</h2>
      </div>

      <div className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">风险等级</span>
          {getRiskBadge(task.risk_level)}
        </div>

        <div>
          <label className="text-sm font-medium">审核备注</label>
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="请输入审核意见（拒绝时必填）"
            rows={4}
            className="mt-1"
          />
        </div>

        <div className="space-y-2">
          <Button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="w-full bg-green-600 hover:bg-green-700"
          >
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : '✓ 批准'}
          </Button>
          <Button onClick={handleReject} disabled={isSubmitting} variant="destructive" className="w-full">
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : '✗ 拒绝'}
          </Button>
        </div>

        <Card className="p-3 bg-gray-50">
          <div className="text-xs text-gray-500 space-y-1">
            <div>管理员ID: {task.user_id}</div>
            <div>API状态: 已连接</div>
          </div>
        </Card>
      </div>
    </div>
  );
}
