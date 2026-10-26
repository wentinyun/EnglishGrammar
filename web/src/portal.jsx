import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * 把弹层挂到 <body> 下。
 *
 * 页面容器上只要出现 animation / transform / filter 之类的东西，就会形成层叠上下文，
 * 里面的 position: fixed 也会改成相对该容器定位——弹层于是既盖不住顶栏底栏，
 * 又会以整页高度为参照居中而跑到视口外。挂到 body 是唯一稳妥的解法。
 */
export default function Portal({ children }) {
  const [host] = useState(() => document.createElement("div"));

  useEffect(() => {
    host.className = "portal-layer";
    document.body.appendChild(host);
    return () => {
      host.remove();
    };
  }, [host]);

  return createPortal(children, host);
}
