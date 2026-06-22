import { THEME_STORAGE_KEY } from "@/lib/theme-constants";

export function ThemeScript() {
  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `try{var t=localStorage.getItem("${THEME_STORAGE_KEY}")||"dark";document.documentElement.setAttribute("data-theme",t);if(t==="dark"){document.documentElement.classList.add("dark")}}catch(e){}`,
      }}
    />
  );
}
