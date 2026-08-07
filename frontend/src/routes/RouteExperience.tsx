import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

import { titleForPath } from "./routeTitles";

export function RouteExperience() {
  const location = useLocation();
  const previousPathname = useRef(location.pathname);

  useEffect(() => {
    document.title = titleForPath(location.pathname);

    if (previousPathname.current !== location.pathname) {
      document.getElementById("main-content")?.focus();
      previousPathname.current = location.pathname;
    }
  }, [location.pathname]);

  return null;
}
