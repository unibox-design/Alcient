import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import LeftNav from "../components/LeftNav";
import SmartSidebar from "../components/SmartSidebar";
import MainEditor from "../components/MainEditor";
import PreviewPanel from "../components/PreviewPanel";
import { initProject } from "../store/projectSlice";

export default function ProjectPage() {
  const { id } = useParams();
  const dispatch = useDispatch();
  const project = useSelector((state) => state.project);
  const [activeTab, setActiveTab] = useState("script");

  useEffect(() => {
    if (!id) return;
    if (project.id !== id) {
      const prettyId = id.charAt(0).toUpperCase() + id.slice(1);
      dispatch(
        initProject({
          id,
          title: `${prettyId} Project`,
          format: "landscape",
          scenes: [],
        })
      );
    }
  }, [dispatch, id, project.id]);

  const projectTitle =
    project.title ||
    (id ? `Alcient — ${id.charAt(0).toUpperCase() + id.slice(1)} Project` : "Alcient Project");

  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <Link
          to="/"
          className="flex items-center gap-2 text-xl font-semibold text-gray-800 hover:text-gray-900 transition"
        >
          <img src="/alcient.svg" alt="Alcient" className="h-8 w-auto" />
          ALCIENT
        </Link>
        <div className="flex items-center gap-4">
          <Link to="/billing" className="text-sm text-gray-500 hover:text-gray-700 transition">
            Usage & Billing
          </Link>
          <Link to="/" className="text-sm text-gray-500 hover:text-gray-700 transition">
            ← Back to Templates
          </Link>
        </div>
      </header>

      {/* Main workspace grid */}
      <main className="flex flex-1 overflow-hidden">
        {/* Column 1: LeftNav */}
        <div className="w-[5%] min-w-[60px] bg-white border-r border-gray-200 flex flex-col">
          <LeftNav active={activeTab} onChange={setActiveTab} />
        </div>

        {/* Column 2: SmartSidebar */}
        <div className="w-[15%] min-w-[200px] bg-white border-r border-gray-200 overflow-y-auto">
          <SmartSidebar active={activeTab} />
        </div>

        {/* Column 3: MainEditor */}
        <div className="w-[40%] bg-gray-50 flex flex-col">
          {/* Make this area scrollable */}
          <div className="flex-1 overflow-y-auto">
            <MainEditor active={activeTab} />
          </div>
        </div>

        {/* Column 4: Preview */}
        <div className="w-[40%] bg-white border-l border-gray-200 overflow-y-auto">
          <PreviewPanel />
        </div>
      </main>
    </div>

  );
}
