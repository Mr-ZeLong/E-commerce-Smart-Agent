import { Button } from '@/components/ui/button';
import { Package, RefreshCw, Truck, Headphones } from 'lucide-react';

interface QuickActionsProps {
  onAction: (action: string) => void;
}

const actions = [
  { id: 'order_status', label: '查询订单', icon: Package },
  { id: 'return_policy', label: '退货政策', icon: RefreshCw },
  { id: 'shipping', label: '运费咨询', icon: Truck },
  { id: 'contact', label: '联系客服', icon: Headphones },
];

export function QuickActions({ onAction }: QuickActionsProps) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {actions.map((action) => (
        <Button
          key={action.id}
          variant="outline"
          size="sm"
          onClick={() => onAction(action.id)}
          className="text-gray-600"
        >
          <action.icon className="h-4 w-4 mr-1" />
          {action.label}
        </Button>
      ))}
    </div>
  );
}
