import { useState, useEffect, useRef } from 'react';
import { Bell, Package, FileText, MessageSquare, CheckCircle, Loader2, ShoppingCart } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { api } from '../api';
import { useNavigate } from 'react-router-dom';

interface Notification {
  id: number;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  link?: string;
}

const notificationIcons: Record<string, any> = {
  rfq_received: FileText,
  rfq_created: FileText,
  quote_received: Package,
  quote_created: Package,
  contract_created: CheckCircle,
  contract_signed: CheckCircle,
  order_created: ShoppingCart,
  order_status: ShoppingCart,
  new_message: MessageSquare,
  system: Bell,
  default: Bell,
};

const notificationColors: Record<string, string> = {
  rfq_received: 'bg-purple-100 text-purple-600',
  rfq_created: 'bg-blue-100 text-blue-600',
  quote_received: 'bg-green-100 text-green-600',
  quote_created: 'bg-teal-100 text-teal-600',
  contract_created: 'bg-emerald-100 text-emerald-600',
  contract_signed: 'bg-green-100 text-green-600',
  order_created: 'bg-orange-100 text-orange-600',
  order_status: 'bg-yellow-100 text-yellow-600',
  new_message: 'bg-indigo-100 text-indigo-600',
  system: 'bg-gray-100 text-gray-600',
  default: 'bg-gray-100 text-gray-600',
};

export default function NotificationDropdown() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (user) {
      fetchNotifications();
      fetchUnreadCount();
      const interval = setInterval(() => {
        fetchUnreadCount();
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [user]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const response = await api.get('/notifications/', { params: { limit: 10 } });
      const data = response.data || [];
      setNotifications(data);
    } catch (error) {
      console.error('Error fetching notifications:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUnreadCount = async () => {
    try {
      const response = await api.get('/notifications/unread-count');
      setUnreadCount(response.data.count || 0);
    } catch (error) {
      console.error('Error fetching unread count:', error);
    }
  };

  const markAsRead = async (id: number) => {
    try {
      // Sử dụng PATCH với body theo API backend
      await api.patch(`/notifications/${id}`, { is_read: true });
      setNotifications(notifications.map(n => 
        n.id === id ? { ...n, is_read: true } : n
      ));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Error marking as read:', error);
    }
  };

  const markAllAsRead = async () => {
    try {
      // Sử dụng POST theo API backend
      await api.post('/notifications/mark-all-read');
      setNotifications(notifications.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error('Error marking all as read:', error);
    }
  };

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.is_read) {
      markAsRead(notification.id);
    }
    setIsOpen(false);

    // Nếu có link thì navigate đến link đó
    if (notification.link) {
      navigate(notification.link);
      return;
    }

    // Nếu không có link thì navigate theo type
    const role = user?.role;
    const basePath = role === 'supplier' ? '/supplier' : role === 'shop' ? '/shop' : '/admin';
    
    switch (notification.type) {
      case 'rfq_received':
      case 'rfq_created':
        navigate(`${basePath}/rfq`);
        break;
      case 'quote_received':
      case 'quote_created':
        navigate(role === 'supplier' ? '/supplier/rfq' : '/shop/rfq');
        break;
      case 'contract_created':
      case 'contract_signed':
        navigate(`${basePath}/contracts`);
        break;
      case 'order_created':
      case 'order_status':
        navigate(`${basePath}/orders`);
        break;
      case 'new_message':
        navigate(`${basePath}/chat`);
        break;
      default:
        break;
    }
  };

  const formatTime = (dateString: string) => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return 'Vừa xong';
      if (diffMins < 60) return `${diffMins} phút trước`;
      if (diffHours < 24) return `${diffHours} giờ trước`;
      if (diffDays < 7) return `${diffDays} ngày trước`;
      return date.toLocaleDateString('vi-VN');
    } catch {
      return '';
    }
  };

  const getIcon = (type: string) => {
    return notificationIcons[type] || notificationIcons.default;
  };

  const getColor = (type: string) => {
    return notificationColors[type] || notificationColors.default;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) fetchNotifications();
        }}
        className="relative p-2 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <Bell className="w-5 h-5 text-gray-600" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-xl shadow-2xl border border-gray-200 z-50 overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-primary-50 to-white">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Bell className="w-4 h-4 text-primary-600" />
              Thông báo
              {unreadCount > 0 && (
                <span className="px-2 py-0.5 bg-red-500 text-white text-xs rounded-full">
                  {unreadCount}
                </span>
              )}
            </h3>
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium hover:underline"
              >
                Đọc tất cả
              </button>
            )}
          </div>

          {/* Notification List */}
          <div className="max-h-[400px] overflow-y-auto">
            {loading ? (
              <div className="py-8 text-center">
                <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary-600" />
                <p className="text-sm text-gray-500 mt-2">Đang tải...</p>
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-12 text-center">
                <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Bell className="w-8 h-8 text-gray-300" />
                </div>
                <p className="text-gray-500 font-medium">Không có thông báo</p>
                <p className="text-sm text-gray-400 mt-1">Các thông báo mới sẽ hiển thị ở đây</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {notifications.map((notification) => {
                  const Icon = getIcon(notification.type);
                  return (
                    <div
                      key={notification.id}
                      onClick={() => handleNotificationClick(notification)}
                      className={`px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors ${
                        !notification.is_read ? 'bg-blue-50/50' : ''
                      }`}
                    >
                      <div className="flex gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${getColor(notification.type)}`}>
                          <Icon className="w-5 h-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p className={`text-sm leading-tight ${!notification.is_read ? 'font-semibold text-gray-900' : 'text-gray-700'}`}>
                              {notification.title}
                            </p>
                            {!notification.is_read && (
                              <span className="w-2 h-2 bg-primary-500 rounded-full flex-shrink-0 mt-1.5"></span>
                            )}
                          </div>
                          {notification.message && (
                            <p className="text-sm text-gray-500 line-clamp-2 mt-0.5">
                              {notification.message}
                            </p>
                          )}
                          <p className="text-xs text-gray-400 mt-1">
                            {formatTime(notification.created_at)}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
              <button
                onClick={() => {
                  setIsOpen(false);
                  const basePath = user?.role === 'supplier' ? '/supplier' : user?.role === 'shop' ? '/shop' : '/admin';
                  navigate(`${basePath}/notifications`);
                }}
                className="w-full text-center text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                Xem tất cả thông báo →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}