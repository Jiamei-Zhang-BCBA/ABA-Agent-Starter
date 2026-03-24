import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center">
      <h1 className="text-6xl font-bold text-gray-300 mb-4">404</h1>
      <p className="text-gray-500 mb-6">页面不存在</p>
      <Link href="/features">
        <Button>返回首页</Button>
      </Link>
    </div>
  );
}
